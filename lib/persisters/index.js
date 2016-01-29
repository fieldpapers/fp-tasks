"use strict";

module.exports.persistTo = (path, options) => {
  options = options || {};

  switch (process.env.PERSIST) {
  case "local":
    return require("./local")(path);

  case "s3":
  default:
    return require("./s3")(Object.assign({}, options, {
      Key: path,
    }));
  }
};
