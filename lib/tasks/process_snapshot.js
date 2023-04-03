/* eslint camelcase:0 */
"use strict";

const assert = require("assert"),
  fs = require("fs"),
  url = require("url"),
  util = require("util");

const async = require("async"),
  AWS = require("aws-sdk"),
  Sentry = require("@sentry/node"),
  request = require("request"),
  tmp = require("tmp");

const persistTo = require("../persisters").persistTo,
  spawn = require("../spawn");

const S3 = new AWS.S3();

const download = function download(imageUrl, filename, callback) {
  const uri = url.parse(imageUrl);
  let imageStream;

  if (uri.hostname.match(/s3.*\.amazonaws\.com/)) {
    let bucket;
    let key;

    // use aws-sdk so we can include credentials when fetching
    if (uri.hostname.match(/.+\.s3.*\.amazonaws\.com/)) {
      const pathname = decodeURIComponent(uri.pathname);

      bucket = uri.hostname.split(".")[0];
      key = pathname.split("/").slice(1).join("/");
    } else {
      const pathname = decodeURIComponent(uri.pathname),
        pathComponents = pathname.split("/").slice(1);

      bucket = pathComponents.shift();
      key = pathComponents.join("/");
    }

    imageStream = S3.getObject({
      Bucket: bucket,
      Key: key
    }).createReadStream();
  } else {
    // assume that it's publicly available on the internet
    imageStream = request(imageUrl);
  }

  imageStream.on("error", callback);

  imageStream.pipe(fs.createWriteStream(filename)
                   .on("finish", callback)
                   .on("error", callback));
};

module.exports = function processSnapshot(payload, callback) {
  const snapshot = payload.snapshot;

  return async.parallel({
    source: async.apply(tmp.tmpName),
    tiff: async.apply(tmp.tmpName)
  }, function(err, filenames) {
    if (err) {
      return callback(err);
    }

    const filename = filenames.source,
      tiffName = filenames.tiff,
      persister = persistTo(`snapshots/${snapshot.slug}/field-paper-${snapshot.slug}.tiff`, {
        ContentType: "image/tiff",
      });

    return async.waterfall([
      async.apply(download, snapshot.image_url, filename),
      function(done) {
        // TODO this probably exits with 0 even if it fails
        const child = spawn("python3", ["process_snapshot.py"], {
          cwd: "/app/decoder",
          timeout: 120e3
        });

        child.on("exit", function(code, signal) {
          if (code === 0) {
            return done();
          }

          if (signal) {
            return done(new Error(util.format("process_snapshot.py was killed by %s", signal)));
          }

          return done(new Error(util.format("process_snapshot.py exited with %s", code)));
        });

        child.stderr.pipe(process.stdout);

        fs.createReadStream(filename).pipe(child.stdin);
        child.stdout.pipe(fs.createWriteStream(tiffName));
      },
      function(done) {
        // TODO this used to decodeURIComponent(data.Location), but that doesn't occur elsewhere
        return persister(fs.createReadStream(tiffName), done);
      }
    ], function(err, geoTiffUrl) {
      // remove the tmp files
      fs.unlink(filename, err => err && console.warn(err.stack));
      fs.unlink(tiffName, err => err && console.warn(err.stack));

      const responsePayload = {
        task: payload.task,
        snapshot: {
          slug: snapshot.slug
        }
      };

      if (err) {
        console.warn(err.stack);
        Sentry.captureException(err);

        responsePayload.error = {
          message: err.message,
          stack: err.stack
        };
      } else {
        responsePayload.snapshot.geotiff_url = geoTiffUrl;
      }

      return callback(null, responsePayload);
    });
  });
};

module.exports.validate = function validate(payload) {
  assert.ok(payload.snapshot, "Payload must include a 'snapshot'.");
  assert.ok(payload.snapshot.slug, "Payload must include 'snapshot.slug'.");
  assert.ok(payload.snapshot.image_url, "Payload must include 'snapshot.image_url'.");
};
