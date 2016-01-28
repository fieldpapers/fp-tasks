"use strict";

const fs = require("fs"),
  path = require("path");

const env = require("require-env"),
  mkdirp = require("mkdirp");

const TARGET_PATH = env.require("STATIC_PATH"),
  TARGET_PREFIX = env.require("STATIC_URI_PREFIX");

module.exports = relativePath => {
  const fullPath = path.join(TARGET_PATH, relativePath);
  let prefix = TARGET_PREFIX;

  if (prefix[prefix.length - 1] !== "/") {
    prefix += "/";
  }

  return (stream, callback) => {
    let writeStream;

    mkdirp(path.dirname(fullPath), err => {
      if (err) {
        return callback(err);
      }

      writeStream = fs.createWriteStream(fullPath, {
        encoding: null
      });

      writeStream.on("error", callback);
      writeStream.on("finish", () => callback(null, `${prefix}${relativePath}`));

      stream.pipe(writeStream);
    });

    return {
      abort: () => {
        if (writeStream) {
          writeStream.end();
          fs.unlink(writeStream.path);
        }
      }
    };
  };
};
