FROM python:3.9

ENV PYTHONUNBUFFERED 1

RUN mkdir /app
RUN mkdir /app/static
RUN mkdir /app/images

WORKDIR /app

COPY requirements.txt /app/
RUN pip install -r requirements.txt

COPY ./bookwyrm /app
COPY ./celerywyrm /app
