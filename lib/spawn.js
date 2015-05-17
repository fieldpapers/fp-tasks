"use strict";

const spawn = require("child_process").spawn;

module.exports = function spawnWithTimeout(command, args, options) {
  const child = spawn.apply(null, arguments);
  child.command = command;
  child.args = args;

  if (options.timeout > 0) {
    const killSignal = options && options.killSignal || "SIGTERM";

    let timeout = setTimeout(function() {
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
