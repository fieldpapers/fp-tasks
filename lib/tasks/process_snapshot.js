/*eslint camelcase:0*/
"use strict";

const assert = require("assert"),
  url = require("url"),
  util = require("util");

const AWS = require("aws-sdk"),
  env = require("require-env"),
  raven = require("raven"),
  request = require("request");

const shell = require("../shell");

const sentry = new raven.Client();

const S3_BUCKET_NAME = env.require("S3_BUCKET_NAME");

AWS.config.update({
  region: process.env.AWS_DEFAULT_REGION || "us-east-1"
});

const S3 = new AWS.S3();

module.exports = function processSnapshot(payload, callback) {
  const snapshot = payload.snapshot,
    cmd = "process_snapshot.py";

  const child = shell(cmd, [], {
    timeout: 120e3
  }, {
    Bucket: S3_BUCKET_NAME,
    Key: util.format("snapshots/%s/walking-paper-%s.tif", snapshot.slug, snapshot.slug),
    ACL: "public-read",
    CacheControl: "public,max-age=31536000",
    ContentType: "image/tiff"
  }, function(err, uri) {
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
      responsePayload.snapshot.geotiff_url = uri;
    }

    return callback(null, responsePayload);
  });

  const uri = url.parse(payload.snapshot.image_url);
  let imageStream;

  if (uri.hostname === "s3.amazonaws.com") {
    // use aws-sdk so we can include credentials when fetching
    const key = uri.pathname.split("/").slice(2).join("/");

    imageStream = S3.getObject({
      Bucket: S3_BUCKET_NAME,
      Key: key
    }).createReadStream().pipe(child.stdin);
  } else {
    // assume that it's publicly available on the internet
    imageStream = request(payload.snapshot.image_url);
  }

  return imageStream.pipe(child.stdin);
};

module.exports.validate = function validate(payload) {
  assert.ok(payload.snapshot, "Payload must include an 'snapshot'.");
  assert.ok(payload.snapshot.slug, "Payload must include 'snapshot.slug'.");
  assert.ok(payload.image_url, "Payload must include 'snapshot.image_url'.");
};
