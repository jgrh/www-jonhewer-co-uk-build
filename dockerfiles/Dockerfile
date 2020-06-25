FROM debian:buster

RUN apt-get update && \
    apt-get install -y apt-transport-https ca-certificates curl gnupg2 --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

RUN curl -sSL "https://deb.nodesource.com/gpgkey/nodesource.gpg.key" | apt-key add - && \
    echo "deb https://deb.nodesource.com/node_14.x buster main" > /etc/apt/sources.list.d/nodesource.list && \
    echo "deb-src https://deb.nodesource.com/node_14.x buster main" >> /etc/apt/sources.list.d/nodesource.list && \
    apt-get update && \
    apt-get install -y nodejs --no-install-recommends && \
    npm install npm@latest -g && \
    rm -rf /var/lib/apt/lists/*

RUN apt-get update && \
    apt-get install -y build-essential ruby ruby-dev --no-install-recommends && \
    gem update --system && \
    gem install compass && \
    rm -rf /var/lib/apt/lists/*

RUN apt-get update && \
    apt-get install -y graphicsmagick --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*
