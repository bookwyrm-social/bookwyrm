FROM python:3.9

ENV PYTHONUNBUFFERED 1

RUN mkdir /app
WORKDIR /app

COPY package.json requirements.txt .stylelintrc.js .stylelintignore /app/
RUN pip install -r requirements.txt

RUN apt-get update && apt-get install -y curl ca-certificates && apt-get clean

ARG NODEVERSION=18.18.0

RUN mkdir -p /usr/local/node-${NODEVERSION} && \
    curl -L https://nodejs.org/dist/v${NODEVERSION}/node-v${NODEVERSION}-linux-x64.tar.xz | tar Jxf - --strip-components 1 -C /usr/local/node-${NODEVERSION} && \
    PATH=/usr/local/node-${NODEVERSION}/bin:$PATH npm install --global yarn
ENV PATH /usr/local/node-${NODEVERSION}/bin:$PATH

RUN npm install .
