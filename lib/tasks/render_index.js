"use strict";

const util = require("util");

const clone = require("clone"),
  env = require("require-env");

const shell = require("../shell");

const API_BASE_URL = process.env.API_BASE_URL || "http://fieldpapers.org/",
  ENV = clone(process.env),
  S3_BUCKET_NAME = env.require("S3_BUCKET_NAME");

ENV.API_BASE_URL = API_BASE_URL;

module.exports = function renderIndex(page, callback) {
  let cmd = "create_index.py",
      args = [
        "-s", page.atlas.paper_size,
        "-l", page.atlas.layout,
        "-o", page.atlas.orientation,
        "-b", page.bbox[3], page.bbox[0], page.bbox[1], page.bbox[2],
        "-e", page.atlas.bbox[3], page.atlas.bbox[0], page.atlas.bbox[1], page.atlas.bbox[2],
        "-z", page.zoom,
        "-p", page.provider.replace(/{s}\./i, ""),
        "-c", page.atlas.cols,
        "-r", page.atlas.rows,
        page.atlas.slug
      ];

  return shell(cmd, args, {
    cwd: "/opt/paper",
    env: ENV,
    killSignal: "SIGKILL",
    timeout: 120e3
  }, {
    Bucket: S3_BUCKET_NAME,
    Key: util.format("prints/%s/atlas-%s.pdf", page.atlas.slug, page.atlas.slug),
    ACL: "public-read",
    CacheControl: "public,max-age=31536000",
    ContentType: "application/pdf"
  }, callback);
};
