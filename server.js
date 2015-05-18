#!/usr/bin/env node
/*eslint camelcase:0 no-process-exit:0*/
"use strict";

const assert = require("assert"),
  util = require("util");

const bodyParser = require("body-parser"),
  changeCase = require("change-case"),
  express = require("express"),
  morgan = require("morgan"),
  raven = require("raven"),
  request = require("request"),
  responseTime = require("response-time");

const tasks = require("./lib/tasks");

const app = express().disable("x-powered-by"),
  sentry = new raven.Client();

if (process.env.NODE_ENV !== "production") {
  app.use(morgan("dev"));
}

app.use(responseTime());

if (process.env.SENTRY_DSN) {
  raven.patchGlobal(function(logged, err) {
    console.log("Uncaught error. Reporting to Sentry and exiting.");
    console.error(err.stack);

    process.exit(1);
  });

  app.use(raven.middleware.express());
}

app.use(bodyParser.json());

app.get("/", function(req, res, next) {
  // this is the SQSd endpoint (which is intended to be synchronous and will
  // probably need to capture all messages on a queue)
  return next();
});


Object.keys(tasks).forEach(function(name) {
  const snake = changeCase.snake(name),
    task = tasks[name];

  app.put(util.format("/%s", snake), function(req, res) {
    const payload = req.body,
      callbackUrl = payload.callback_url;

    // validation
    try {
      assert.equal(snake, payload.task, util.format("Task ('%s') does not match endpoint (%s).", payload.task, snake));
      assert.ok(callbackUrl, "Payload must include 'callback_url'.");

      if (task.validate) {
        // TODO validate payload using JSON schemas (https://github.com/tdegrunt/jsonschema)
        task.validate(payload);
      }
    } catch (err) {
      return res.status(400).json({
        error: err.message
      });
    }

    // fire and forget
    task(payload, function(err, rsp) {
      if (err) {
        sentry.captureError(err);
        return console.error(err.stack);
      }

      return request.post({
        body: rsp,
        json: true,
        uri: callbackUrl
      }, function(err, rsp, body) {
        if (err) {
          console.warn(err);
          sentry.captureError(err);
          return;
        }

        if (rsp.statusCode < 200 || rsp.statusCode >= 300) {
          console.warn("%s returned %d: %s", callbackUrl, rsp.statusCode, body);
          sentry.captureMessage(util.format("%s returned %d: %s", callbackUrl, rsp.statusCode, body));
        }
      });
    });

    return res.status(202).send();
  });
});

app.listen(process.env.PORT || 8080, function() {
  console.log("Listening at http://%s:%d/", this.address().address, this.address().port);
});
