FROM python:3.9.2-slim-buster

ENV PYTHONUNBUFFERED=1 \
    LANG=C.UTF-8 \
    APP_DIR=/app \
    DOCKERIZED=true

RUN mkdir $APP_DIR

RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get install -y \
        bash gettext libgettextpo-dev libjpeg-dev zlib1g-dev \
        python3-dev python3-setuptools gcc libpq-dev\
    && apt-get clean \
    && pip install --upgrade pip \
    && pip install -I poetry

RUN rm /bin/sh && ln -s /bin/bash /bin/sh
RUN mkdir $APP_DIR/static $APP_DIR/images

WORKDIR $APP_DIR

COPY pyproject.toml poetry.lock ./
RUN poetry install --no-dev

COPY ./bookwyrm ./celerywyrm ${APP_DIR}/

