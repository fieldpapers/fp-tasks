import assert from "assert";
import {execFile} from "child_process";
import url from "url";
import util from "util";

import async from "async";
import AWS from "aws-sdk";
import Sentry from "@sentry/node";
import request from "request";
import xml2js from "xml2js";

const S3 = new AWS.S3();

const createImageStream = function createImageStream(imageUrl) {
  const uri = url.parse(imageUrl);
  let imageStream;

  if (uri.hostname.match(/s3.*\.amazonaws\.com/)) {
    let bucket;
    let key;

    // use aws-sdk so we can include credentials when fetching
    if (uri.hostname.match(/.+\.s3.*\.amazonaws\.com/)) {
      const pathname = decodeURIComponent(uri.pathname);

      bucket = uri.hostname.split(".")[0];
      key = pathname.split("/").slice(1).join("/");
    } else {
      const pathname = decodeURIComponent(uri.pathname),
        pathComponents = pathname.split("/").slice(1);

      bucket = pathComponents.shift();
      key = pathComponents.join("/");
    }

    imageStream = S3.getObject({
      Bucket: bucket,
      Key: key
    }).createReadStream();
  } else {
    // assume that it's publicly available on the internet
    imageStream = request(imageUrl);
  }

  return imageStream;
};

export function fetchSnapshotMetadata(payload, _callback) {
  let finished = false;
  const snapshot = payload.snapshot,
    imageStream = createImageStream(snapshot.image_url),
    callback = function() {
      if (!finished) {
        finished = true;

        return _callback.apply(null, arguments);
      }
    };

  imageStream.on("error", callback);

  return async.waterfall([
    function(done) {
      const child = execFile("/app/decoder/read_qr_code.sh", [], {
        timeout: 120e3
      }, function(err, stdout, stderr) {
        if (err) {
          err.stderr = stderr;
          return done(err);
        }

        return done(null, decodeURIComponent(stdout.trim()));
      });

      imageStream.pipe(child.stdin);
    },
    function(pageUrl, done) {
      return request.get({
        headers: {
          // TOOD implement support for JSON responses and prefer those
          // Accept: "application/json, application/paperwalking+xml"
          Accept: "application/paperwalking+xml"
        },
        uri: pageUrl
      }, function(err, rsp, body) {
        if (err) {
          return done(err);
        }

        if (rsp.statusCode < 200 || rsp.statusCode >= 300) {
          return done(new Error(util.format("%s returned %d:", pageUrl, rsp.statusCode, rsp.body)));
        }

        switch (rsp.headers["content-type"].split(";").shift()) {
        case "application/paperwalking+xml":
          return xml2js.parseString(body, function(err, doc) {
            if (err) {
              return done(err);
            }

            const bounds = doc.print.bounds[0];
            let pvt = false;

            if (doc.print.private) {
              try {
                pvt = JSON.parse(doc.print.private[0]);
              } catch (err) {
                console.warn("Failed to parse '%s'", doc.print.private[0]);
              }
            }

            return done(null, {
              bbox: [+bounds.west[0], +bounds.south[0], +bounds.east[0], +bounds.north[0]],
              page_url: pageUrl,
              private: pvt,
              zoom: doc.print.center[0].zoom[0] | 0
            });
          });

        default:
          // JSON
          return done(new Error("Not implemented"));
        }
      });
    }
  ], function(err, metadata) {
    const responsePayload = {
      task: payload.task,
      snapshot: {
        slug: snapshot.slug
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
      Object.keys(metadata).forEach(function(k) {
        responsePayload.snapshot[k] = metadata[k];
      });
    }

    return callback(null, responsePayload);
  });
}

fetchSnapshotMetadata.validate = function validate(payload) {
  assert.ok(payload.snapshot, "Payload must include a 'snapshot'.");
  assert.ok(payload.snapshot.slug, "Payload must include 'snapshot.slug'.");
  assert.ok(payload.snapshot.image_url, "Payload must include 'snapshot.image_url'.");
};
