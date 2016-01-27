/* eslint no-ternary:0 */
"use strict";

const util = require("util");

const _debug = require("debug");

const spawn = require("./spawn");

const debug = _debug("fieldpapers-tasks:shell");

module.exports = function shell(cmd, args, spawnOptions, persister, _callback) {
  spawnOptions.encoding = "encoding" in spawnOptions ? spawnOptions.encoding : null;
  spawnOptions.env = spawnOptions.env || process.env;
  spawnOptions.killSignal = spawnOptions.killSignal || "SIGTERM";
  spawnOptions.timeout = "timeout" in spawnOptions ? spawnOptions.timeout : 0;

  // prevent callback from being called multiple times
  let finished = false;
  const callback = function() {
    if (!finished) {
      finished = true;

      return _callback.apply(null, arguments);
    }
  };

  debug(cmd, args.join(" "));

  // use spawn and handle our own timeouts to prevent output from being
  // buffered (and likely surpassing execFile's maxBuffer size)
  const child = spawn(cmd, args, spawnOptions);

  const upload = persister(child.stdout, callback);
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

  return child;
};
