FROM node:18.15

ENV NODE_ENV=production
ENV HOME=/app
ENV AWS_REGION=us-east-1

# System dependencies:
# - build-essential/pkg-config/libpython3-dev: build the blobdetector C++ extension
# - gdal/cairo/zbar: the Python geo + QR stack (gdal pin in requirements.txt must
#   match this image's libgdal; bullseye ships 3.2.2)
# - ghostscript/imagemagick/qrencode/php-cli: CLI tools the render jobs shell out
#   to; php runs decoder/lossy/page.php, the FPDF-based PDF writer (still live)
RUN DEBIAN_FRONTEND=noninteractive apt-get update && \
    apt-get install -y --no-install-recommends \
      git-core build-essential pkg-config \
      python3-pip libpython3-dev \
      gdal-bin libgdal-dev libcairo2-dev \
      ghostscript imagemagick qrencode zbar-tools php-cli \
      libpq-dev libxmlsec1 libxmlsec1-dev && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY blobdetector /app/blobdetector
COPY decoder/requirements.txt /app/decoder/requirements.txt
RUN python3 -m pip install -r /app/decoder/requirements.txt

COPY package.json package-lock.json /app/
RUN npm ci --omit=dev

COPY . /app/

RUN chown -R node:node /app
USER node

EXPOSE 8080
CMD ["node", "server.js"]
