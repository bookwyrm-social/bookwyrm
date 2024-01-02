FROM python:3.9
WORKDIR /app/dev-tools

ENV PATH="/app/dev-tools/node_modules/.bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV NPM_CONFIG_UPDATE_NOTIFIER=false
ENV PIP_ROOT_USER_ACTION=ignore PIP_DISABLE_PIP_VERSION_CHECK=1

COPY nodejs.pref /etc/apt/preferences.d/
COPY nodejs.sources /etc/apt/sources.list.d/
COPY package.json requirements.txt .stylelintrc.js .stylelintignore /app/dev-tools/

RUN apt-get update            && \
    apt-get install -y nodejs && \
    pip install -r requirements.txt && \
    npm install .

WORKDIR /app
