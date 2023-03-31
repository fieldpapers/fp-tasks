FROM quay.io/fieldpapers/paper:v0.7.0

ENV DEBIAN_FRONTEND noninteractive

RUN \
  apt-get update && \
  apt-get upgrade -y && \
  apt-get clean

ENV NODE_VERSION=16.16.0
RUN apt install -y curl
RUN curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.3/install.sh | bash
ENV NVM_DIR=/root/.nvm
RUN . "$NVM_DIR/nvm.sh" && nvm install ${NODE_VERSION}
RUN . "$NVM_DIR/nvm.sh" && nvm use v${NODE_VERSION}
RUN . "$NVM_DIR/nvm.sh" && nvm alias default v${NODE_VERSION}
ENV PATH="/root/.nvm/versions/node/v${NODE_VERSION}/bin/:${PATH}"
RUN node --version
RUN npm --version

ENV HOME /app
ENV PORT 8080
ENV NODE_ENV production
ENV AWS_REGION us-east-1
WORKDIR /app

ADD package.json /app/

RUN npm install

ADD . /app/

VOLUME /app
EXPOSE 8080

CMD npm start
