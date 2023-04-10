import assert from "assert";

import clone from "clone";
import Sentry from "@sentry/node";

import persistTo from "../persisters/index.js";
import shell from "../shell.js";

const API_BASE_URL = process.env.API_BASE_URL || "https://fieldpapers.org/",
  ENV = clone(process.env);

ENV.API_BASE_URL = API_BASE_URL;

export function renderIndex(payload, callback) {
  const page = payload.page,
    cmd = "python3",
    args = [
      "create_index.py",
      "-s", page.atlas.paper_size,
      "-l", page.atlas.layout,
      "-o", page.atlas.orientation,
      "-b", page.bbox[3], page.bbox[0], page.bbox[1], page.bbox[2],
      "-e", page.atlas.bbox[3], page.atlas.bbox[0], page.atlas.bbox[1], page.atlas.bbox[2],
      "-z", page.zoom,
      // strip out subdomain placeholders and uppercase the rest
      "-p", page.provider.replace(/{s}/i, "a").replace(/(\{\w\})/g, function(x) {
        return x.toUpperCase();
      }).replace("@2x", "").replace(/,$/, ""),
      "-c", page.atlas.cols,
      "-r", page.atlas.rows,
      "-t", page.atlas.text,
      "-T", page.atlas.title || "",
      page.atlas.slug
    ],
    persister = persistTo(`atlases/${page.atlas.slug}/${page.atlas.slug}-index.pdf`);

  return shell(cmd, args, {
    cwd: "/app/decoder",
    env: ENV,
    killSignal: "SIGKILL",
    timeout: 60e3
  }, persister, function(err, uri) {
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
      Sentry.captureException(err);

      responsePayload.error = {
        message: err.message,
        stack: err.stack
      };
    } else {
      responsePayload.page.pdf_url = uri;
    }

    return callback(null, responsePayload);
  });
}

renderIndex.validate = function validate(payload) {
  assert.ok(payload.page, "Payload must include a 'page'.");
};
