FROM python:3.11

ENV PYTHONUNBUFFERED 1

RUN mkdir /app /app/static /app/images

WORKDIR /app

RUN apt-get update && apt-get install -y gettext libgettextpo-dev tidy && apt-get clean

COPY pyproject.toml /app/
RUN pip install "pip>=25.1.0" --no-cache-dir && pip install --group main --group dev --no-cache-dir

COPY entrypoint.sh /entrypoint.sh

# Entrypoint script is used to do database migrations and collectstatic
ENTRYPOINT ["/entrypoint.sh"]
