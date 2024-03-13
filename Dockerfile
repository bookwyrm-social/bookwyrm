FROM python:3.11

ENV PYTHONUNBUFFERED 1

RUN mkdir /app /app/static /app/images

WORKDIR /app

RUN apt-get update && apt-get install -y gettext libgettextpo-dev tidy && apt-get clean

COPY requirements.txt /app/
RUN pip install -r requirements.txt --no-cache-dir
