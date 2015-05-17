"use strict";

const fs = require("fs"),
  util = require("util");

const async = require("async"),
  env = require("require-env"),
  request = require("request"),
  tmp = require("tmp");

const shell = require("../shell");

tmp.setGracefulCleanup();

const S3_BUCKET_NAME = env.require("S3_BUCKET_NAME");

module.exports = function mergePages(atlas, _callback) {
  const cmd = "gs",
    files = [],
    cleanup = function cleanup() {
      return files.forEach(function(filename) {
        fs.unlink(filename);
      });
    };

  let args = [
        "-q",
        "-sDEVICE=pdfwrite",
        "-o", "-"
      ];

  const callback = function() {
    cleanup();

    return _callback.apply(null, arguments);
  };

  return async.map(atlas.pages, function(page, done) {
    return tmp.file({
      prefix: "page-",
      postfix: ".pdf"
    }, function(err, path, fd) {
      if (err) {
        return done(err);
      }

      files.push(path);

      const writeStream = fs.createWriteStream(path, {
        fd
      });

      writeStream.on("finish", function() {
        return done(null, path);
      });

      request
        .get(page.pdf_url)
        .on("error", done)
        .pipe(writeStream);
    });
  }, function(err, filenames) {
    if (err) {
      return callback(err);
    }

    args = args.concat(filenames);

    return shell(cmd, args, {
      timeout: 120e3
    }, {
      Bucket: S3_BUCKET_NAME,
      Key: util.format("prints/%s/atlas-%s.pdf", atlas.slug, atlas.slug),
      ACL: "public-read",
      CacheControl: "public,max-age=31536000",
      ContentType: "application/pdf"
    }, callback);
  });
};
