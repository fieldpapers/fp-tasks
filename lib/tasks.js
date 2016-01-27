"use strict";
/* eslint no-sync:0 */

const fs = require("fs"),
  path = require("path");

module.exports = fs.readdirSync(path.join(__dirname, "tasks")).map(function(filename) {
  return require(path.join(__dirname, "tasks", filename));
}).reduce(function(tasks, mod) {
  tasks[mod.name] = mod;

  return tasks;
}, {});
