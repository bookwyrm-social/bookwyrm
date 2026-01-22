FROM postgres:latest

RUN apt update && apt install -y shellcheck

COPY ./tests/testing-entrypoint.sh /testing-entrypoint.sh
RUN chmod u+rx,go=r /testing-entrypoint.sh
COPY ./weed.sh /weed.sh
RUN chmod u+rx,go=r /weed.sh