FROM node:16.16

ENV DEBIAN_FRONTEND noninteractive

# Python stuff
RUN \
  apt-get update && \
  apt-get upgrade -y && \
  apt-get clean
RUN \
  apt-get install -y git-core build-essential && \
  apt-get clean
RUN \
  apt-get install -y ghostscript gdal-bin python3-gdal libpython3-dev pkg-config python3-pip libcairo2-dev php-cli qrencode zbar-tools imagemagick libpq-dev libxmlsec1 libxmlsec1-dev && \
  apt-get clean

ENV HOME /app
ENV NODE_ENV production
ENV AWS_REGION us-east-1
WORKDIR /app

COPY package.json /app/

RUN npm install

COPY blobdetector /app/blobdetector
COPY decoder/requirements.txt /app/decoder/requirements.txt

# https://stackoverflow.com/questions/56357794/unable-to-install-grpcio-using-pip-install-grpcio
#RUN pip3 install --upgrade pip
#RUN python3 -m pip install --upgrade setuptools
#RUN pip3 install --no-cache-dir  --force-reinstall -Iv grpcio==1.53.0

RUN python3 -m pip install -r /app/decoder/requirements.txt

COPY . /app/

EXPOSE 8080

CMD npm start
