FROM centos
LABEL maintainer="Demetrius Bell <meetri@gmail.com>"
RUN yum install -y epel-release \
    && yum groupinstall -y "Development Tools"

RUN mkdir /opt/build \
    && cd /opt/build \
    && curl -LO http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz \
    && tar -xvzf ta-lib-0.4.0-src.tar.gz \
    && cd ta-lib \
    && ./configure \
    && make install 

RUN yum update -y \
    && yum install -y https://centos7.iuscommunity.org/ius-release.rpm \
    && yum install -y python36u python36u-devel python36u-pip tmux vim npm \
    && pip3.6 install --upgrade pip \
    && pip3.6 install psycopg2 influxdb redis pg numpy ta-lib flask pyyaml pymongo cherrypy cherrypy-cors twilio

RUN curl -o- https://raw.githubusercontent.com/creationix/nvm/v0.33.2/install.sh | bash

RUN source /root/.bashrc \
    && nvm install node

RUN npm install redis pg node.bittrex.api

RUN npm install console-stamp
ENV LD_LIBRARY_PATH=/usr/local/lib

RUN ln -s /usr/bin/python3.6 /usr/bin/python3
ENV CRYPTO_LIB=/opt/libs/cryptolib-master

COPY . /opt

WORKDIR /opt/bot/
ENTRYPOINT ["/usr/bin/python3.6" "-u" "/opt/bot/serve.py"]
