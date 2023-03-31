/* eslint camelcase:0 */
"use strict";

const assert = require("assert"),
  fs = require("fs");

const async = require("async"),
  Sentry = require("@sentry/node"),
  request = require("request"),
  tmp = require("tmp");

const persistTo = require("../persisters").persistTo,
  shell = require("../shell");

tmp.setGracefulCleanup();

module.exports = function mergePages(payload, _callback) {
  const atlas = payload.atlas,
    cmd = "gs",
    files = [],
    cleanup = function cleanup() {
      return files.forEach(function(filename) {
        fs.unlink(filename, err => err && console.warn(err.stack));
      });
    },
    persister = persistTo(`atlases/${atlas.slug}/atlas-${atlas.slug}.pdf`);

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
    }, persister, function(err, uri) {
      const responsePayload = {
        task: payload.task,
        atlas: {
          slug: atlas.slug
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
        responsePayload.atlas.pdf_url = uri;
      }

      return callback(null, responsePayload);
    });
  });
};

module.exports.validate = function validate(payload) {
  assert.ok(payload.atlas, "Payload must include an 'atlas'.");
};
