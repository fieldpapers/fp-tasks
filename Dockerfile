FROM debian:bullseye-slim AS base

ENV HOME=/app
ENV AWS_REGION=us-east-1

# System dependencies:
# - build-essential/pkg-config/libpython3-dev: build the blobdetector C++ extension
#   (and gdal/pycairo, which pip builds from source)
# - gdal/cairo/zbar: the Python geo + QR stack (gdal pin in requirements.txt must
#   match this image's libgdal; bullseye ships 3.2.2)
# - ghostscript/imagemagick/qrencode: CLI tools the service and decoder scripts
#   shell out to
# - fonts-liberation2: Liberation Sans, the font on rendered pages (via fontconfig)
#
# bullseye is past end of life and its packages are only on archive.debian.org.
RUN sed -i 's|deb.debian.org|archive.debian.org|g' /etc/apt/sources.list && \
    DEBIAN_FRONTEND=noninteractive apt-get update && \
    apt-get install -y --no-install-recommends \
      ca-certificates build-essential pkg-config \
      python3 python3-pip libpython3-dev \
      gdal-bin libgdal-dev libcairo2-dev \
      ghostscript imagemagick qrencode zbar-tools fonts-liberation2 && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY blobdetector /app/blobdetector
COPY requirements.txt /app/requirements.txt
RUN python3 -m pip install -r /app/requirements.txt

COPY . /app/

RUN useradd --home-dir /app app && chown -R app:app /app
USER app


# Regression tests; see `make test`. Runs as root so tests can write to the
# bind-mounted working copy.
FROM base AS test

USER root
RUN python3 -m pip install pytest==8.4.2 httpx==0.28.1


FROM base AS production

EXPOSE 8080
CMD ["sh", "-c", "exec uvicorn service.app:app --host 0.0.0.0 --port ${PORT:-8080}"]
