FROM python:3.11-bookworm
WORKDIR /app/dev-tools

ENV PATH="/app/dev-tools/node_modules/.bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV NPM_CONFIG_UPDATE_NOTIFIER=false
ENV PIP_ROOT_USER_ACTION=ignore
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

COPY --from=node:18-slim /usr/local/bin /usr/local/bin
COPY --from=node:18-slim /usr/local/lib/node_modules /usr/local/lib/node_modules
COPY package.json requirements.txt .stylelintrc.js .stylelintignore /app/dev-tools/

RUN pip install --no-cache-dir -r requirements.txt && \
    npm install .

WORKDIR /app
