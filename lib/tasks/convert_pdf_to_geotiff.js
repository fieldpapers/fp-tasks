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

module.exports = function convertPdfToGeoTIFF(payload, callback) {
  const page = payload.page;

  const convert = spawn("convert", [
    "-density", "288",   // 4x 72ppi
    "-",
    "-shave", "144x144", // 0.5in x 0.5in
    "-chop", "0x144",    // 0 x 0.5in
    "-flatten",          // also sets the background to white
    "png24:-"            // force 24-bit RGBA PNG
  ], {
    timeout: 120e3
  });

  // TODO use tmp
  let filename = "/tmp/whatever.tiff";

  const gdalTranslate = spawn("gdal_translate", [
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

  const _stderr = [];

  gdalTranslate.stderr.on("data", function(chunk) {
    _stderr.push(chunk);
  });

  request
    .get(page.pdf_url)
    .on("error", function(err) {
      console.warn(err.stack);
    })
    .pipe(convert.stdin);

  convert.stdout.pipe(gdalTranslate.stdin);

  convert.on("error", function(err) {
    console.error("convert:", err);
  });

  gdalTranslate.on("error", function(err) {
    console.error("gdal_translate:", err);
  });

  gdalTranslate.on("exit", function(code, signal) {
    if (code !== 0 || signal) {
      const stderr = Buffer.concat(_stderr).toString();
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

    return S3.upload({
      Bucket: S3_BUCKET_NAME,
      Key: util.format("prints/%s/%s-%s.tiff", page.atlas.slug, page.atlas.slug, page.page_number),
      ACL: "public-read",
      CacheControl: "public,max-age=31536000",
      ContentType: "image/tiff",
      Body: fs.createReadStream(filename)
    }, function(err, data) {
      if (err) {
        return callback(err);
      }

      return callback(null, data.Location);
    });
  });
};

module.exports.validate = function validate(payload) {
  assert.ok(payload.page, "Payload must include a 'page'.");
};
