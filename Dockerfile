FROM python:3.11 AS build

ENV PYTHONUNBUFFERED=1
ENV PATH=/venv/bin:$PATH

RUN apt-get update && apt-get install -y gettext libpq5 tidy libsass1 libsass-dev && apt-get clean
# libsass doesn't provide arm64 wheel and takes ~25min to compile in github action
# So tell libsass-python to use system installed libsass instead compiling one in build phase
# and build takes as whole ~2min in arm64 github action
ENV SYSTEM_SASS=True

WORKDIR /app


RUN python -mvenv /venv
COPY requirements.txt /app/
RUN pip install -r requirements.txt --no-cache-dir


FROM python:3.11-slim
RUN addgroup --system app && adduser --system --group bookwyrm
RUN apt-get update && apt-get install -y gettext libpq5 tidy libsass1 gosu && apt-get clean
WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV PATH=/venv/bin:$PATH
ENV SYSTEM_SASS=True

COPY --from=build /app /app
COPY --from=build /venv /venv
COPY README.md LICENSE.md VERSION /app/
COPY manage.py gunicorn.conf.py /app/
COPY celerywyrm /app/celerywyrm
COPY locale /app/locale
COPY bookwyrm /app/bookwyrm
COPY entrypoint.sh /entrypoint.sh

EXPOSE 8000
VOLUME ["/app/exports", "/app/images", "/app/static"]

ENTRYPOINT [ "/entrypoint.sh" ]
CMD ["gunicorn", "bookwyrm.wsgi:application"]
