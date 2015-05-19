/*eslint camelcase:0*/
"use strict";

const assert = require("assert"),
  fs = require("fs"),
  url = require("url"),
  util = require("util");

const async = require("async"),
  AWS = require("aws-sdk"),
  env = require("require-env"),
  raven = require("raven"),
  request = require("request"),
  tmp = require("tmp");

const spawn = require("../spawn");

const sentry = new raven.Client();

const S3_BUCKET_NAME = env.require("S3_BUCKET_NAME");

AWS.config.update({
  region: process.env.AWS_DEFAULT_REGION || "us-east-1"
});

const S3 = new AWS.S3();

const download = function download(uri, filename, callback) {
  uri = url.parse(uri);
  let imageStream;

  if (uri.hostname === "s3.amazonaws.com") {
    // use aws-sdk so we can include credentials when fetching
    const key = uri.pathname.split("/").slice(2).join("/");

    imageStream = S3.getObject({
      Bucket: S3_BUCKET_NAME,
      Key: key
    }).createReadStream();
  } else {
    // assume that it's publicly available on the internet
    imageStream = request(uri);
  }

  imageStream.pipe(fs.createWriteStream(filename)
                   .on("finish", callback)
                   .on("error", callback));
};

module.exports = function processSnapshot(payload, callback) {
  const snapshot = payload.snapshot;

  return tmp.tmpName(function(err, filename) {
    if (err) {
      return callback(err);
    }

    return async.waterfall([
      async.apply(download, snapshot.image_url),
      function(done) {
        const child = spawn("process_snapshot.py", [], {
          timeout: 120e3
        }, done);

        fs.createReadStream(filename).pipe(child.stdin);
      },
      function(tiffName, cb) {
        return async.parallel({
          pageUrl: function(done) {
            const child = spawn("zbarimg", [
              "--raw",
              "-q",
              ":-" // zbar uses ImageMagick internally, so :- is stdin
            ], {
              encoding: "utf8",
              timeout: 120e3
            }, done);

            fs.createReadStream(filename).pipe(child.stdin);
          },
          geoTiffUrl: function(done) {
            return S3.upload({
              Bucket: S3_BUCKET_NAME,
              Key: util.format("snapshots/%s/walking-paper-%s.tif", snapshot.slug, snapshot.slug),
              ACL: "public-read",
              CacheControl: "public,max-age=31536000",
              ContentType: "image/tiff",
              Body: fs.createReadStream(tiffName)
            }, function(err, data) {
              if (err) {
                return done(err);
              }

              return done(null, data.Location);
            });
          },
          bbox: function(done) {
            // TODO read w/ gdal
            // OR fetch from the API endpoint along with zoom and private

            return done();
          }
        }, function() {
          // remove the tmp files
          fs.unlink(filename);
          fs.unlink(tiffName);

          // pass all arguments on
          return cb.apply(null, arguments);
        });
      }
      // create read stream, get url
      // create read stream, process
      // get extent (as 4326)
      // create read stream, upload
    ], function(err, data) {
      const responsePayload = {
        task: payload.task,
        snapshot: {
          slug: snapshot.slug
        }
      };

      if (err) {
        console.warn(err.stack);
        sentry.captureError(err);

        responsePayload.error = {
          message: err.message,
          stack: err.stack
        };
      } else {
        // TODO decodeURI()? trim()?
        console.log("pageUrl:", data.pageUrl);

        responsePayload.snapshot.geotiff_url = data.geoTiffUrl;
        responsePayload.snapshot.bbox = data.bbox;
        // TODO rename this in the JSON representation
        responsePayload.snapshot.print_href = data.pageUrl;
      }

      return callback(null, responsePayload);
    });
  });
};

module.exports.validate = function validate(payload) {
  assert.ok(payload.snapshot, "Payload must include an 'snapshot'.");
  assert.ok(payload.snapshot.slug, "Payload must include 'snapshot.slug'.");
  assert.ok(payload.image_url, "Payload must include 'snapshot.image_url'.");
};
