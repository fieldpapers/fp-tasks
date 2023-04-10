import {relativePath} from "./local.js";
import {s3options} from "./s3.js";

export default function persistTo(path, options) {
  options = options || {};

  switch (process.env.PERSIST) {
  case "local":
    return relativePath(path);

  case "s3":
  default:
    return s3options(Object.assign({}, options, {
      Key: path,
    }));
  }
}
