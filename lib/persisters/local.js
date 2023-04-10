import fs from "fs";
import path from "path";

import env from "require-env";
import { mkdirp } from "mkdirp";

export function relativePath(relPath) {
  const TARGET_PATH = env.require("STATIC_PATH"),
    TARGET_PREFIX = env.require("STATIC_URI_PREFIX");

  const fullPath = path.join(TARGET_PATH, relPath);
  let prefix = TARGET_PREFIX;

  if (prefix[prefix.length - 1] !== "/") {
    prefix += "/";
  }

  return (stream, _callback) => {
    let writeStream;

    // prevent callback from being called multiple times
    let finished = false;
    const callback = function() {
      if (!finished) {
        finished = true;

        return _callback.apply(null, arguments);
      }
    };

    mkdirp(path.dirname(fullPath)).then(err => {
      if (err) {
        return callback(err);
      }

      writeStream = fs.createWriteStream(fullPath, {
        encoding: null
      });

      writeStream.on("error", callback);
      writeStream.on("finish", () => callback(null, `${prefix}${relPath}`));

      stream.pipe(writeStream);
    });

    return {
      abort: (err) => {
        // pass errors first
        callback(err);

        // now clean up
        if (writeStream) {
          writeStream.end();
          fs.unlink(writeStream.path, err => err && console.warn(err.stack));
        }
      }
    };
  };
}
