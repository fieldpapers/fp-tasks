import { spawn as node_spawn } from "child_process";

export default function spawn(command, args, options) {
  // create a new process group
  options.detached = true;

  const child = node_spawn(command, args, options);
  child.command = command;
  child.args = args;

  if (options.timeout > 0) {
    const killSignal = options && options.killSignal || "SIGTERM";

    let timeout = setTimeout(function() {
      child.stdout.destroy();
      child.stderr.destroy();

      try {
        process.kill(-child.pid, killSignal);
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
}
