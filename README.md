# fp-tasks

## Running

This is intended to be run from a Docker image. `-v $(pwd):/app` facilitates
local development, `--env-file` propagates environment variables into the
container.  See `.env.sample` for sample `.env` file.

```bash
docker run --rm \
  -p 8080:8080 \
  -v $(pwd):/app \
  --env-file .env \
  fieldpapers/tasks
```

## Environment variables

* `AWS_REGION` - AWS region. Required if using S3.
* `S3_BUCKET_NAME` - S3 bucket name. Required if using S3.
* `API_BASE_URL` - Base Field Papers API URL (used when generating QR codes and
  titles). Defaults to `http://fieldpapers.org/`.
* `PERSIST` - File persistence. Can be `local` or `s3`. Defaults to `s3`.
* `STATIC_PATH` - Path to write static files to. Must be HTTP-accessible for
  page merging to work. Required if using `local` persistence.
* `STATIC_URI_PREFIX` - Prefix to apply to static paths (e.g.
  http://example.org/path) to allow them to resolve. Required if using `local`
  persistence.
