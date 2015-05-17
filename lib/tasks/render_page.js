"use strict";

const util = require("util");

const clone = require("clone"),
  env = require("require-env");

const shell = require("../shell");

const API_BASE_URL = process.env.API_BASE_URL || "http://fieldpapers.org/",
  ENV = clone(process.env),
  S3_BUCKET_NAME = env.require("S3_BUCKET_NAME");

ENV.API_BASE_URL = API_BASE_URL;

module.exports = function renderPage(page, callback) {
  const cmd = "create_page.py",
    args = [
      "-s", page.atlas.paper_size,
      "-l", page.atlas.layout,
      "-o", page.atlas.orientation,
      "-b", page.bbox[3], page.bbox[0], page.bbox[1], page.bbox[2],
      "-n", page.page_number,
      "-z", page.zoom,
      "-p", page.provider.replace(/{s}\./i, ""),
      page.atlas.slug
    ];

  return shell(cmd, args, {
    cwd: "/opt/paper",
    env: ENV,
    killSignal: "SIGKILL",
    timeout: 120e3
  }, {
    Bucket: S3_BUCKET_NAME,
    Key: util.format("prints/%s/%s-%s.pdf", page.atlas.slug, page.atlas.slug, page.page_number),
    ACL: "public-read",
    CacheControl: "public,max-age=31536000",
    ContentType: "application/pdf"
  }, callback);
};
