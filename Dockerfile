FROM debian:stretch
MAINTAINER Luca Lianas luca.lianas@crs4.it

RUN apt-get update && apt-get install -y python \
    python-pip \
    git \
    libopencv-dev \
    libopenslide-dev

WORKDIR /opt

RUN git clone https://github.com/crs4/odin.git

WORKDIR /opt/odin

RUN pip install -r requirements.txt

CMD bash
