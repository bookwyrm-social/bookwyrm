FROM postgres:latest

# crontab
RUN mkdir /backups
COPY ./backup.sh /backups
COPY ./cronfile /etc/cron.d/cronfile
RUN apt-get update && apt-get -y install cron
RUN chmod 0644 /etc/cron.d/cronfile
RUN crontab /etc/cron.d/cronfile
RUN touch /var/log/cron.log
