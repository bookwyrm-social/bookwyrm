FROM python:3.11 AS build

ENV PYTHONUNBUFFERED=1
ENV PATH=/venv/bin:$PATH

WORKDIR /app

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked --mount=type=cache,target=/var/lib/apt,sharing=locked apt-get update && apt-get install -y gettext libgettextpo-dev tidy libpq5 libsass-dev

# libsass doesn't provide arm64 wheel and takes ~25min to compile in github action
# So tell libsass-python to use system installed libsass instead compiling one in build phase
# and build takes as whole ~2min in arm64 github action
ENV SYSTEM_SASS=True

RUN python -mvenv /venv

COPY pyproject.toml /app/
RUN --mount=type=cache,target=/root/.cache/pip pip install "pip>=25.1.0" && pip install --group main --group dev

FROM python:3.11-slim
WORKDIR /app

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked --mount=type=cache,target=/var/lib/apt,sharing=locked apt-get update && apt-get install -y gettext tidy libpq5 libsass1 curl
ENV PYTHONUNBUFFERED=1
ENV PATH=/venv/bin:$PATH
ENV SYSTEM_SASS=True

COPY --from=build /venv /venv
COPY --from=build /app /app

COPY entrypoint.sh /entrypoint.sh
COPY README.md LICENSE.md VERSION /app/
COPY manage.py gunicorn.conf.py /app/
COPY celerywyrm /app/celerywyrm
COPY locale /app/locale
COPY bookwyrm /app/bookwyrm

RUN python3 -mcompileall /app/bookwyrm /app/celerywyrm /app/manage.py /app/gunicorn.conf.py

VOLUME ["/app/exports", "/app/images", "/app/static"]

# Entrypoint script is used to do database migrations and collectstatic
ENTRYPOINT ["/entrypoint.sh"]
