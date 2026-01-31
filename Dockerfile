FROM python:3.11

ENV PYTHONUNBUFFERED 1

RUN mkdir /app /app/static /app/images

WORKDIR /app

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked --mount=type=cache,target=/var/lib/apt,sharing=locked apt-get update && apt-get install -y gettext libgettextpo-dev tidy

COPY pyproject.toml /app/
RUN --mount=type=cache,target=/root/.cache/pip pip install "pip>=25.1.0" && pip install --group main --group dev

COPY entrypoint.sh /entrypoint.sh

# Entrypoint script is used to do database migrations and collectstatic
ENTRYPOINT ["/entrypoint.sh"]
