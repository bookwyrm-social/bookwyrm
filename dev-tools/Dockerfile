FROM python:3.9

ENV PYTHONUNBUFFERED 1
ENV PIP_ROOT_USER_ACTION ignore

WORKDIR /app

RUN apt-get update && apt-get install -y curl
RUN curl -sL https://deb.nodesource.com/setup_18.x | bash -
RUN apt-get install -y nodejs && apt-get clean

RUN python -m pip install --upgrade pip

COPY requirements.txt ./
RUN pip install -r requirements.txt

WORKDIR /app/dev-tools
ENV NO_UPDATE_NOTIFIER true
COPY package.json .stylelintrc.js .stylelintignore ./
RUN npm install
