FROM postgres:latest

# crontab
RUN mkdir /backups
COPY ./db_backup.sh /backups
COPY ./db-backups-cron /etc/cron.d/db-backups-cron
RUN apt-get update && apt-get -y install cron
RUN chmod 0644 /etc/cron.d/db-backups-cron
RUN crontab /etc/cron.d/db-backups-cron
RUN touch /var/log/cron.log
