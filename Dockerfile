FROM python:3.11

ENV PYTHONUNBUFFERED 1

RUN mkdir /app /app/static /app/images

WORKDIR /app

RUN apt-get update && apt-get install -y gettext libgettextpo-dev tidy && apt-get clean

COPY requirements.txt /app/
RUN pip install -r requirements.txt --no-cache-dir
COPY README.md LICENSE.md VERSION /app/
COPY manage.py gunicorn.conf.py /app/
COPY celerywyrm /app/celerywyrm
COPY bookwyrm /app/bookwyrm
COPY locale /app/locale


FROM python:3.11-slim
RUN addgroup --system app && adduser --system --group bookwyrm
RUN apt-get update && apt-get install -y gettext libpq5 tidy libsass1 && apt-get clean
WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV PATH=/venv/bin:$PATH

COPY --from=build /app /app
COPY --from=build /venv /venv

ENTRYPOINT [ "/app/bookwyrm/setup.sh" ]
