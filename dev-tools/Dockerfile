FROM python:3.9

ENV PYTHONUNBUFFERED 1

RUN mkdir /app
WORKDIR /app

COPY package.json requirements.txt .stylelintrc.js .stylelintignore /app/
RUN pip install -r requirements.txt

RUN apt-get update && apt-get install -y curl
RUN curl -sL https://deb.nodesource.com/setup_17.x | bash -
RUN apt-get install -y nodejs && apt-get clean
RUN npm install .
