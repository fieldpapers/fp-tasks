/*eslint camelcase:0*/
"use strict";

const assert = require("assert"),
  util = require("util");

const clone = require("clone"),
  env = require("require-env"),
  raven = require("raven");

const shell = require("../shell");

const sentry = new raven.Client();

const API_BASE_URL = process.env.API_BASE_URL || "http://fieldpapers.org/",
  ENV = clone(process.env),
  S3_BUCKET_NAME = env.require("S3_BUCKET_NAME");

ENV.API_BASE_URL = API_BASE_URL;

module.exports = function renderPage(payload, callback) {
  const page = payload.page,
    cmd = "create_page.py",
    args = [
      "-s", page.atlas.paper_size,
      "-l", page.atlas.layout,
      "-o", page.atlas.orientation,
      "-b", page.bbox[3], page.bbox[0], page.bbox[1], page.bbox[2],
      "-n", page.page_number,
      "-z", page.zoom,
      // strip out subdomain placeholders and uppercase the rest
      "-p", page.provider.replace(/{s}/i, "a").replace(/(\{\w\})/g, function(x) {
        return x.toUpperCase();
      }).replace("@2x", "").replace(/,$/, ""),
      "-t", page.atlas.text,
      page.atlas.slug
    ];

  return shell(cmd, args, {
    cwd: "/opt/paper",
    env: ENV,
    killSignal: "SIGKILL",
    timeout: 120e3
  }, {
    Bucket: S3_BUCKET_NAME,
    Key: util.format("atlases/%s/%s-%s.pdf", page.atlas.slug, page.atlas.slug, page.page_number),
    ACL: "public-read",
    CacheControl: "public,max-age=31536000",
    ContentType: "application/pdf"
  }, function(err, uri) {
    const responsePayload = {
      task: payload.task,
      page: {
        page_number: payload.page.page_number,
        atlas: {
          slug: payload.page.atlas.slug
        }
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
      responsePayload.page.pdf_url = uri;
    }

    return callback(null, responsePayload);
  });
};

module.exports.validate = function validate(payload) {
  assert.ok(payload.page, "Payload must include a 'page'.");
};
