"use strict";

const AWS = require("aws-sdk"),
  env = require("require-env");

const S3 = new AWS.S3();

const S3_BUCKET_NAME = env.require("S3_BUCKET_NAME"),
  S3_DEFAULT_OPTIONS = {
    Bucket: S3_BUCKET_NAME,
    ACL: "public-read",
    CacheControl: "public,max-age=31536000",
    ContentType: "application/pdf",
  };

module.exports = s3options => {
  const options = Object.assign({}, S3_DEFAULT_OPTIONS, s3options);

  return (stream, callback) => {
    options.Body = stream;

    const upload = S3.upload(options, (err, data) => {
      if (err) {
        if (err.code === "RequestAbortedError") {
          // TODO remove the special-casing here
          // request was aborted; an error was already raised on child exit
          return;
        }

        return callback(err);
      }

      return callback(null, data.Location);
    });

    return {
      abort: upload.abort
    };
  };
};
