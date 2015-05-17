"use strict";

const util = require("util");

const AWS = require("aws-sdk"),
  clone = require("clone"),
  env = require("require-env");

const spawn = require("../spawn");

AWS.config.update({
  region: process.env.AWS_DEFAULT_REGION || "us-east-1"
});

const API_BASE_URL = process.env.API_BASE_URL || "http://fieldpapers.org/",
  ENV = clone(process.env),
  S3 = new AWS.S3(),
  S3_BUCKET_NAME = env.require("S3_BUCKET_NAME");

ENV.API_BASE_URL = API_BASE_URL;

module.exports = function renderPage(page, _callback) {
  let finished = false;

  const cmd = "/opt/paper/create_page.py",
    args = [
      "-s", page.atlas.paper_size,
      "-l", page.atlas.layout,
      "-o", page.atlas.orientation,
      "-b", page.bbox[3], page.bbox[0], page.bbox[1], page.bbox[2],
      "-n", page.page_number,
      "-z", page.zoom,
      "-p", page.provider.replace(/{s}\./i, ""),
      page.atlas.slug
    ],
    // prevent callback from being called multiple times
    callback = function() {
      if (!finished) {
        finished = true;

        return _callback.apply(null, arguments);
      }
    };

  // use spawn and handle our own timeouts to prevent output from being
  // buffered (and likely surpassing execFile's maxBuffer size)
  let child = spawn(cmd, args, {
    cwd: "/opt/paper",
    encoding: null,
    env: ENV,
    killSignal: "SIGKILL",
    timeout: 120e3
  });

  let upload = S3.upload({
    Bucket: S3_BUCKET_NAME,
    Key: util.format("prints/%s/atlas-%s.pdf", page.atlas.slug, page.atlas.slug),
    ACL: "public-read",
    Body: child.stdout,
    CacheControl: "public,max-age=31536000",
    ContentType: "application/pdf"
  }, function(err, data) {
    if (err) {
      if (err.code === "RequestAbortedError") {
        // request was aborted; an error was already raised on child exit
        return;
      }

      return callback(err);
    }

    return callback(null, data.Location);
  });

  const _stderr = [];

  child.stderr.on("data", function(chunk) {
    _stderr.push(chunk);
  });

  child.on("error", function(err) {
    console.warn("%s: %s %s", err, cmd, args.join(" "));
  });

  child.on("exit", function(code, signal) {
    if (code !== 0 || signal) {
      upload.abort();

      const stderr = Buffer.concat(_stderr).toString();
      let err;

      if (signal) {
        err = new Error(util.format("Exited after %s: %s %s", signal, cmd, args.join(" ")));
        err.stderr = stderr;

        return callback(err);
      }

      err = new Error(util.format("Exited with %s: %s %s", code, cmd, args.join(" ")));
      err.stderr = stderr;

      return callback(err);
    }
  });
};
