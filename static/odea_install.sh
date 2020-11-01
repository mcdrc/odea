#!/usr/bin/sh

apt install \
  python3 \
  python3-pip \
  pandoc \
  imagemagick \
  libreoffice \
  wkhtmltopdf \
  inkscape \
  ffmpeg

# preview generator
apt install \
  scribus \
  python3-pythonmagick \
  zlib1g-dev \
  libjpeg-dev \
  xvfb \
  poppler-utils \
  libfile-mimeinfo-perl \
  qpdf \
  libimage-exiftool-perl \
  ufraw-batch

pip3 install odea
