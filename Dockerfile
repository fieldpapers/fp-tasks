FROM quay.io/fieldpapers/paper:v0.4.0

ENV DEBIAN_FRONTEND noninteractive

RUN \
  apt-get update && \
  apt-get upgrade -y && \
  apt-get clean

RUN \
  apt-get install -y libnss-mdns && \
  apt-get clean

RUN \
  sed -i -e 's/#enable-dbus=yes/enable-dbus=no/' /etc/avahi/avahi-daemon.conf && \
  sed -i -e 's/rlimit-nproc=3//' /etc/avahi/avahi-daemon.conf


RUN \
  apt-get install -y software-properties-common apt-transport-https curl lsb-release && \
  add-apt-repository "deb https://deb.nodesource.com/iojs_2.x $(lsb_release -c -s) main" && \
  (curl -s https://deb.nodesource.com/gpgkey/nodesource.gpg.key | apt-key add -) && \
  apt-get update && \
  apt-get install -y iojs && \
  apt-get clean

ENV HOME /app
ENV PORT 8080
WORKDIR /app

ADD package.json /app/

RUN \
  npm install && \
  npm cache clean

ADD . /app/

VOLUME /app
EXPOSE 8080

CMD avahi-daemon -D && npm start
