FROM postgres:17

# crontab
RUN apt-get update && apt-get -y install cron

RUN mkdir /backups
COPY ./backup.sh /usr/local/bin/bookwyrm-backup.sh
COPY ./weed.sh /usr/local/bin/bookwyrm-weed.sh
COPY ./cronfile /etc/cron.d/cronfile
COPY entrypoint.sh /entrypoint.sh
RUN chmod 0644 /etc/cron.d/cronfile

# Tell cron to run foreground and log to stdout
ENTRYPOINT ["/entrypoint.sh"]

CMD ["cron","-f","-L","7"]
