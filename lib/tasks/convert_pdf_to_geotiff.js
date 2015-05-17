/*eslint camelcase:0*/
"use strict";

const assert = require("assert"),
  fs = require("fs"),
  util = require("util");

const AWS = require("aws-sdk"),
  env = require("require-env"),
  request = require("request"),
  tmp = require("tmp");

const spawn = require("../spawn");

const S3_BUCKET_NAME = env.require("S3_BUCKET_NAME");

AWS.config.update({
  region: process.env.AWS_DEFAULT_REGION || "us-east-1"
});

const S3 = new AWS.S3();

const spawnAndCaptureStdErr = function spawnAndCaptureStdErr() {
  const child = spawn.apply(null, arguments);

  // collect stderr for later diagnostics
  child._stderr = [];

  child.stderr.on("data", function(chunk) {
    child._stderr.push(chunk);
  });

  return child;
};

module.exports = function convertPdfToGeoTIFF(payload, _callback) {
  const page = payload.page;

  // prevent callback from being called multiple times (return the value from
  // the first one)
  let finished = false;
  const callback = function() {
    if (!finished) {
      finished = true;

      return _callback.apply(null, arguments);
    }
  };

  return tmp.tmpName(function(err, filename) {
    if (err) {
      return callback(err);
    }

    const errorHandler = function errorHandler(err) {
      const e = new Error(util.format("%s failed with %s", this.command, err));
      e.stderr = Buffer.concat(this._stderr).toString();

      return callback(e);
    };

    const exitHandler = function exitHandler(code, signal) {
      if (code !== 0 || signal) {
        const stderr = Buffer.concat(this._stderr).toString();
        let err;

        if (signal) {
          err = new Error(util.format("Exited after %s: %s %s", signal, this.command, this.args.join(" ")));
          err.stderr = stderr;

          return callback(err);
        }

        err = new Error(util.format("Exited with %s: %s %s", code, this.command, this.args.join(" ")));
        err.stderr = stderr;

        return callback(err);
      }
    };

    const convert = spawnAndCaptureStdErr("convert", [
      "-density", "288",   // 4x 72ppi
      "-",
      "-shave", "144x144", // 0.5in x 0.5in
      "-chop", "0x144",    // 0 x 0.5in
      "-flatten",          // also sets the background to white
      "png24:-"            // force 24-bit RGBA PNG
    ], {
      timeout: 120e3
    });

    const gdalTranslate = spawnAndCaptureStdErr("gdal_translate", [
      "-of", "GTIFF",
      "-a_srs", "EPSG:4326",
      "-a_ullr", page.bbox[0], page.bbox[3], page.bbox[1], page.bbox[2],
      "-co", "TILED=yes",
      "-co", "COMPRESS=deflate",
      "/vsistdin/",
      filename
    ], {
      timeout: 120e3
    });

    // fetch the PDF and pipe it into convert
    request
      .get(page.pdf_url)
      .on("error", function(err) {
        return callback(err);
      })
      .pipe(convert.stdin);

    // pipe the output of convert into gdal_translate
    convert.stdout.pipe(gdalTranslate.stdin);

    // wire up error and exit handlers

    convert.on("error", errorHandler);
    gdalTranslate.on("error", errorHandler);

    convert.on("exit", exitHandler);
    gdalTranslate.on("exit", exitHandler);

    gdalTranslate.on("exit", function(code) {
      if (code === 0) {
        return S3.upload({
          Bucket: S3_BUCKET_NAME,
          Key: util.format("prints/%s/%s-%s.tiff", page.atlas.slug, page.atlas.slug, page.page_number),
          ACL: "public-read",
          CacheControl: "public,max-age=31536000",
          ContentType: "image/tiff",
          Body: fs.createReadStream(filename)
        }, function(err, data) {
          // remove the tmp file
          fs.unlink(filename);

          if (err) {
            return callback(err);
          }

          return callback(null, data.Location);
        });
      }
    });
  });
};

module.exports.validate = function validate(payload) {
  assert.ok(payload.page, "Payload must include a 'page'.");
};
