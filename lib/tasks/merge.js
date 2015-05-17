"use strict";

const fs = require("fs"),
  util = require("util");

const async = require("async"),
  AWS = require("aws-sdk"),
  request = require("request"),
  tmp = require("tmp");

const spawn = require("../spawn");

AWS.config.update({
  region: process.env.AWS_DEFAULT_REGION || "us-east-1"
});

tmp.setGracefulCleanup();

const S3 = new AWS.S3();

module.exports = function merge(atlas, _callback) {
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
      ],
      finished = false;

  // prevent callback from being called multiple times
  const callback = function() {
    if (!finished) {
      finished = true;

      cleanup();

      return _callback.apply(null, arguments);
    }
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

    // use spawn and handle our own timeouts to prevent output from being
    // buffered (and likely surpassing execFile's maxBuffer size)
    let child = spawn(cmd, args, {
      encoding: null,
      timeout: 120e3
    });

    let upload = S3.upload({
      Bucket: "data.stamen.com",
      Key: "tmp/whatever-all.pdf",
      ACL: "public-read",
      Body: child.stdout,
      CacheControl: "public,max-age=31536000",
      ContentType: "application/pdf"
    }, function(err, data) {
      if (err) {
        if (err.code === "RequestAbortedError") {
          // request was aborted; an error was/will be already raised on child exit
          return;
        }

        return callback(err);
      }

      return callback(null, data.Location);
    });

    child.stderr.pipe(process.stderr);

    child.on("error", function(err) {
      console.warn("%s: %s %s", err, cmd, args.join(" "));
    });

    child.on("exit", function(code, signal) {
      if (code !== 0 || signal) {
        upload.abort();

        if (signal) {
          return callback(new Error(util.format("Exited after %s: %s %s", signal, cmd, args.join(" "))));
        }

        return callback(new Error(util.format("Exited with %s: %s %s", code, cmd, args.join(" "))));
      }
    });
  });
};
