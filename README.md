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
* `AWS_ACCESS_KEY_ID` - AWS key with read/write access to the configured S3
  bucket(s).
* `AWS_SECRET_ACCESS_KEY` - Corresponding secret.
* `API_BASE_URL` - Base Field Papers API URL (used when generating QR codes and
  titles). Defaults to `https://fieldpapers.org/`.
* `PERSIST` - File persistence. Can be `local` or `s3`. Defaults to `s3`.
* `STATIC_PATH` - Path to write static files to. Must be HTTP-accessible for
  page merging to work. Required if using `local` persistence.
* `STATIC_URI_PREFIX` - Prefix to apply to static paths (e.g.
  http://example.org/path) to allow them to resolve. Required if using `local`
  persistence.

## Quick links
- [🔗 fieldpapers.org](https://fieldpapers.org)
- [📋 Project overview](https://github.com/fieldpapers)
- [🐞 Issues and bug reports](https://github.com/fieldpapers/fieldpapers/issues)
- [🌐 Translations](https://explore.transifex.com/fieldpapers/fieldpapers/)
- [🤝 Code of Conduct](https://wiki.openstreetmap.org/wiki/Foundation/Local_Chapters/United_States/Code_of_Conduct_Committee/OSM_US_Code_of_Conduct)
