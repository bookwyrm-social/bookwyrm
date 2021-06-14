FROM python:3.9

ENV PYTHONUNBUFFERED 1

RUN mkdir /app /app/static /app/images

WORKDIR /app

COPY requirements.txt /app/
RUN pip install -r requirements.txt --no-cache-dir
RUN apt-get update && apt-get install -y gettext libgettextpo-dev && apt-get clean
