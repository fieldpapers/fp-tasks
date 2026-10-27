# fp-tasks

Renders Field Papers atlas pages to PDF and georeferences uploaded snapshots
for [fp-web](https://github.com/fieldpapers/fp-web).

## API

| Endpoint | Input | Output |
|----------|-------|--------|
| `POST /render_page` | `slug`, `page_number`, `bbox`, `zoom`, `provider`, `paper_size`, `orientation`, `layout`, `text`, `title` | `{pdf_url}` |
| `POST /render_index` | the same, plus `atlas_bbox`, `cols`, `rows` | `{pdf_url}` |
| `POST /merge_pages` | `slug`, `pdf_urls` (in order) | `{pdf_url}` |
| `POST /decode_qr` | `image_url` | `{href}` |
| `POST /georeference` | `slug` (of the snapshot), `image_url`, `bbox`, `paper_size`, `orientation`, `layout` (of the page) | `{geotiff_url}` |
| `GET /health` | | `{}` |

Endpoints are synchronous; `fp-web` calls these from background jobs. Bounding boxes are `[west, south, east, north]`.

## Running

This is intended to be run from a container image:

```bash
podman build -t fp-tasks .
podman run --rm -p 8080:8080 --env-file .env fp-tasks
```

For local development it is usually run by fp-web's `docker-compose.yml`. See
`.env.sample` for a sample `.env` file.

The service has no authentication and must not be exposed publicly.

## Tests

`tests/` holds end-to-end tests of the HTTP API: rendering atlas pages
(against generated map tiles), merging them, and georeferencing both
rasterized pages and photos of printed pages (`tests/snapshots/`, listed in
`tests/snapshots.json`). They run in the container image's `test` stage:

```bash
make test                       # or: make test PYTEST_ARGS="-k round_trip -x"
```

Images produced by the tests are written to `tests/actual/` and compared with
`tests/expected/`. After an intentional change to the output, run
`make test PYTEST_ARGS=--update-expected` and review the changed images.

## Environment variables

* `PORT` - Port to listen on. Defaults to `8080`.
* `AWS_REGION` - AWS region. Required if using S3.
* `S3_BUCKET_NAME` - S3 bucket name. Required if using S3.
* `AWS_ACCESS_KEY_ID` - AWS key with read/write access to the configured S3
  bucket(s).
* `AWS_SECRET_ACCESS_KEY` - Corresponding secret.
* `API_BASE_URL` - Base Field Papers URL (used when generating QR codes and
  titles). Defaults to `https://fieldpapers.org/`.
* `PERSIST` - File persistence. Can be `local` or `s3`. Defaults to `s3`.
* `STATIC_PATH` - Path to write static files to. Required if using `local`
  persistence.
* `STATIC_URI_PREFIX` - Prefix to apply to static paths (e.g.
  http://example.org/path) to allow them to resolve. Must be HTTP-accessible
  from this service for page merging to work. Required if using `local`
  persistence.

## Quick links
- [🔗 fieldpapers.org](https://fieldpapers.org)
- [📋 Project overview](https://github.com/fieldpapers)
- [🐞 Issues and bug reports](https://github.com/fieldpapers/fieldpapers/issues)
- [🌐 Translations](https://explore.transifex.com/fieldpapers/fieldpapers/)
- [🤝 Code of Conduct](https://wiki.openstreetmap.org/wiki/Foundation/Local_Chapters/United_States/Code_of_Conduct_Committee/OSM_US_Code_of_Conduct)
