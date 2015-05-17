"use strict";

const util = require("util");

const AWS = require("aws-sdk"),
  clone = require("clone");

const spawn = require("../spawn");

AWS.config.update({
  region: process.env.AWS_DEFAULT_REGION || "us-east-1"
});

const API_BASE_URL = process.env.API_BASE_URL || "http://fieldpapers.org/",
  ENV = clone(process.env),
  S3 = new AWS.S3();

ENV.API_BASE_URL = API_BASE_URL;

module.exports = function renderPage(page, callback) {
  callback = callback || function(err) {
    if (err) {
      console.error(err.stack);
      // TODO trigger callback w/ error state
      return;
    }

    console.log(arguments);

    // TODO make HTTP request to web hook to update the state of the atlas
    // (where does this url come from?)
  };

  let cmd = "/opt/paper/create_page.py",
      args = [
        "-s", page.atlas.paper_size,
        "-l", page.atlas.layout,
        "-o", page.atlas.orientation,
        "-b", page.north, page.west, page.south, page.east,
        "-n", page.page_number,
        "-z", page.zoom,
        "-p", page.provider.replace(/{s}\./i, ""),
        page.atlas.slug
      ];

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
    Bucket: "data.stamen.com",
    Key: "tmp/whatever.pdf",
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
};
