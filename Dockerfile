FROM debian:trixie-slim AS base

ENV HOME=/app
ENV AWS_REGION=us-east-1

# All Python dependencies are Debian packages, so their bindings always match
# the system libraries:
# - gdal/cairo/numpy/pil/scipy/zxing-cpp: georeferencing, drawing, image processing,
#   and QR decoding
# - fastapi/uvicorn/boto3: the HTTP service and S3 storage
# - urllib3: map tile downloads
# - ghostscript/qrencode: CLI tools the service and decoder scripts shell out to
# - fonts-liberation: Liberation Sans, the font on rendered pages (via fontconfig)
RUN DEBIAN_FRONTEND=noninteractive apt-get update && \
    apt-get install -y --no-install-recommends \
      ca-certificates python3 \
      python3-gdal python3-cairo python3-numpy python3-pil python3-scipy python3-zxing-cpp \
      python3-fastapi python3-uvicorn python3-boto3 python3-urllib3 \
      ghostscript qrencode fonts-liberation && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY . /app/

RUN useradd --home-dir /app app && chown -R app:app /app
USER app


# Test runner; see `make test`. Runs as root so that tests can write to a
# bind-mounted output directory.
FROM base AS test

USER root
RUN DEBIAN_FRONTEND=noninteractive apt-get update && \
    apt-get install -y --no-install-recommends python3-pytest python3-httpx && \
    rm -rf /var/lib/apt/lists/*


FROM base AS production

EXPOSE 8080
CMD ["sh", "-c", "exec python3 -m uvicorn service.app:app --host 0.0.0.0 --port ${PORT:-8080}"]
