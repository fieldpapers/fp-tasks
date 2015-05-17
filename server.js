#!/usr/bin/env node
"use strict";

const assert = require("assert"),
  util = require("util");

const bodyParser = require("body-parser"),
  express = require("express"),
  morgan = require("morgan"),
  raven = require("raven"),
  request = require("request"),
  responseTime = require("response-time");

const mergePages = require("./lib/tasks/merge_pages"),
  renderIndex = require("./lib/tasks/render_index"),
  renderPage = require("./lib/tasks/render_page");

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

app.put("/merge_pages", function(req, res) {
  const payload = req.body;

  // validation
  // TODO validate payload using JSON schemas (https://github.com/tdegrunt/jsonschema)
  try {
    assert.equal("merge_pages", payload.task, util.format("Task ('%s') does not match endpoint (merge_pages).", payload.task));
    assert.ok(payload.atlas, "Payload must include an 'atlas'.");
    assert.ok(payload.callback_url, "Payload must include 'callback_url'.");
  } catch (err) {
    return res.status(400).json({
      error: err.message
    });
  }

  // fire and forget
  mergePages(payload.atlas, function(err, atlasUrl) {
    const responsePayload = {
      task: payload.task,
      atlas: {
        slug: payload.atlas.slug
      }
    };

    if (err) {
      console.warn(err.stack);
      sentry.captureError(err);

      responsePayload.error = {
        message: err.message,
        stack: err.stack
      };
    } else {
      /*eslint camelcase:0*/
      responsePayload.atlas.pdf_url = atlasUrl;
    }

    return request.post({
      body: responsePayload,
      json: true,
      uri: payload.callback_url
    }, function(err, rsp, body) {
      if (err) {
        console.warn(err);
        sentry.captureError(err);
        return;
      }

      if (rsp.statusCode < 200 || rsp.statusCode >= 300) {
        console.warn("%s returned %d: %s", payload.callback_url, rsp.statusCode, body);
        sentry.captureMessage(util.format("%s returned %d: %s", payload.callback_url, rsp.statusCode, body));
      }
    });
  });

  return res.status(202).send();
});

app.put("/render_index", function(req, res) {
  const payload = req.body;

  // validation
  // TODO validate payload using JSON schemas (https://github.com/tdegrunt/jsonschema)
  try {
    assert.equal("render_index", payload.task, util.format("Task ('%s') does not match endpoint (render_index).", payload.task));
    assert.ok(payload.page, "Payload must include a 'page'.");
    assert.ok(payload.callback_url, "Payload must include 'callback_url'.");
  } catch (err) {
    return res.status(400).json({
      error: err.message
    });
  }

  // fire and forget
  renderIndex(payload.page, function(err, pageUrl) {
    const responsePayload = {
      task: payload.task,
      page: {
        page_number: payload.page.page_number,
        atlas: {
          slug: payload.page.atlas.slug
        }
      }
    };

    if (err) {
      console.warn(err.stack);
      sentry.captureError(err);

      responsePayload.error = {
        message: err.message,
        stack: err.stack
      };
    } else {
      /*eslint camelcase:0*/
      responsePayload.page.pdf_url = pageUrl;
    }

    return request.post({
      body: responsePayload,
      json: true,
      uri: payload.callback_url
    }, function(err, rsp, body) {
      if (err) {
        console.warn(err);
        sentry.captureError(err);
        return;
      }

      if (rsp.statusCode < 200 || rsp.statusCode >= 300) {
        console.warn("%s returned %d: %s", payload.callback_url, rsp.statusCode, body);
        sentry.captureMessage(util.format("%s returned %d: %s", payload.callback_url, rsp.statusCode, body));
      }
    });
  });

  return res.status(202).send();
});

app.put("/render_page", function(req, res) {
  const payload = req.body;

  // validation
  // TODO validate payload using JSON schemas (https://github.com/tdegrunt/jsonschema)
  try {
    assert.equal("render_page", payload.task, util.format("Task ('%s') does not match endpoint (render_page).", payload.task));
    assert.ok(payload.page, "Payload must include a 'page'.");
    assert.ok(payload.callback_url, "Payload must include 'callback_url'.");
  } catch (err) {
    return res.status(400).json({
      error: err.message
    });
  }

  // fire and forget
  renderPage(payload.page, function(err, pageUrl) {
    const responsePayload = {
      task: payload.task,
      page: {
        page_number: payload.page.page_number,
        atlas: {
          slug: payload.page.atlas.slug
        }
      }
    };

    if (err) {
      console.warn(err.stack);
      sentry.captureError(err);

      responsePayload.error = {
        message: err.message,
        stack: err.stack
      };
    } else {
      /*eslint camelcase:0*/
      responsePayload.page.pdf_url = pageUrl;
    }

    return request.post({
      body: responsePayload,
      json: true,
      uri: payload.callback_url
    }, function(err, rsp, body) {
      if (err) {
        console.warn(err);
        sentry.captureError(err);
        return;
      }

      if (rsp.statusCode < 200 || rsp.statusCode >= 300) {
        console.warn("%s returned %d: %s", payload.callback_url, rsp.statusCode, body);
        sentry.captureMessage(util.format("%s returned %d: %s", payload.callback_url, rsp.statusCode, body));
      }
    });
  });

  return res.status(202).send();
});

app.listen(process.env.PORT || 8080, function() {
  console.log("Listening at http://%s:%d/", this.address().address, this.address().port);
});
