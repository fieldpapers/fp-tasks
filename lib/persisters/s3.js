"use strict";

const AWS = require("aws-sdk"),
  clone = require("clone");

const S3 = new AWS.S3();

module.exports = s3options => {
  return (stream, callback) => {
    const options = clone(s3options);
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
    }
  };
};
