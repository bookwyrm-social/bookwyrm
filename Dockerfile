FROM python:3.11 AS build-image



RUN apt-get update && apt-get install -y gettext libgettextpo-dev tidy && apt-get clean

WORKDIR /app

COPY requirements.txt /app/
RUN python -mvenv /venv
ENV PATH=/venv/bin:$PATH
RUN pip install --compile -r requirements.txt --no-cache-dir


FROM python:3.11-slim

RUN apt-get update && apt-get install -y gettext libpq5 tidy && apt-get clean

RUN mkdir -p /app/images /app/static



RUN addgroup --system app && adduser --system --group bookwyrm
RUN mkdir -p /app/static /app/images && chown bookwyrm:bookwyrm /app/static /app/images
WORKDIR /app
USER bookwyrm
COPY --from=build-image /venv /venv
ENV PYTHONUNBUFFERED=1
ENV PATH=/venv/bin:$PATH
