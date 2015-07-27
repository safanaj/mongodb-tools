FROM python:2
MAINTAINER Marco Bardelli

RUN apt-get -y update

ADD mongodbtools /tmp/mongodb-tools/mongodbtools
ADD setup.py /tmp/mongodb-tools/
ADD requirements.txt /tmp/mongodb-tools/

WORKDIR /tmp/mongodb-tools
RUN pip2 install -r requirements.txt
RUN python2 setup.py install

WORKDIR /
RUN rm -rf /tmp/mongodb-tools
RUN apt-get autoremove --purge -y
RUN rm -rf /var/lib/apt/lists/*
RUN rm -rf /var/cache/apt/archives/*
