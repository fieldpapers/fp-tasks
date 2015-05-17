#!/usr/bin/env node
"use strict";

const bodyParser = require("body-parser"),
    express = require("express"),
    morgan = require("morgan"),
    responseTime = require("response-time");

const renderPage = require("./lib/tasks/render_page");

const app = express().disable("x-powered-by");

if (process.env.NODE_ENV !== "production") {
  app.use(morgan("dev"));
}

app.use(responseTime());

if (process.env.SENTRY_DSN) {
  let raven = require("raven");

  raven.patchGlobal(function(logged, err) {
    console.log("Uncaught error. Reporting to Sentry and exiting.");
    console.error(err.stack);

    /*eslint no-process-exit:0*/
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

app.put("/render", function(req, res, next) {
  console.log("body:", req.body);
  renderPage(req.body);

  return res.status(202).send("hello");
});

app.listen(process.env.PORT || 8080, function() {
  console.log("Listening at http://%s:%d/", this.address().address, this.address().port);
});
