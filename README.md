# fp-tasks

## Running

This is intended to be run from a Docker image. `-v $(pwd):/app` facilitates
local development, `--env-file` propagates environment variables into the
container.

```bash
docker run --rm \
  -p 8080:8080 \
  -v $(pwd):/app \
  --env-file .env \
  fieldpapers/tasks
```
