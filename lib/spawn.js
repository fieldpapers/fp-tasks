"use strict";

const spawn = require("child_process").spawn;

module.exports = function spawnWithTimeout(command, args, options) {
  let child = spawn.apply(null, arguments);

  if (options.timeout > 0) {
    let killSignal = options && options.killSignal || "SIGTERM",
        timeout = setTimeout(function() {
          child.stdout.destroy();
          child.stderr.destroy();

          try {
            child.kill(killSignal);
          } catch (err) {
            console.warn(err.stack);
          }
          timeout = null;
        }, options.timeout);

    child.on("exit", function() {
      if (timeout) {
        clearTimeout(timeout);
        timeout = null;
      }
    });
  }

  return child;
};
