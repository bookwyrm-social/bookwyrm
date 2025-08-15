FROM ghcr.io/bookwyrm/bookwyrm:main
USER root
WORKDIR /app/


COPY --from=node:18-slim /usr/local/bin /usr/local/bin
COPY --from=node:18-slim /usr/local/lib/node_modules /usr/local/lib/node_modules
COPY package.json .stylelintrc.js .stylelintignore /app/dev-tools/

ENV PATH="/app/dev-tools/node_modules/.bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV NPM_CONFIG_UPDATE_NOTIFIER=false

RUN pip install "pip>=25.1.0" && pip install --group dev --no-cache-dir
WORKDIR /app/dev-tools
RUN npm install .
WORKDIR /app/

ENTRYPOINT []
CMD []
