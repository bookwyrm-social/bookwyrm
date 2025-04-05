FROM localhost/bookwyrm:latest
USER root
WORKDIR /app/

ENV PATH="/app/dev-tools/node_modules/.bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV NPM_CONFIG_UPDATE_NOTIFIER=false
ENV PIP_ROOT_USER_ACTION=ignore PIP_DISABLE_PIP_VERSION_CHECK=1

COPY --from=node:18-slim /usr/local/bin /usr/local/bin
COPY --from=node:18-slim /usr/local/lib/node_modules /usr/local/lib/node_modules
COPY package.json .stylelintrc.js .stylelintignore /app/dev-tools/
COPY requirements.dev-tools /app/

RUN pip install -r requirements.dev-tools
WORKDIR /app/dev-tools
RUN npm install .
WORKDIR /app/

ENTRYPOINT []
CMD ["bash"]
