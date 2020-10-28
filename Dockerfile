FROM python:3
ENV  PYTHONUNBUFFERED 1
RUN mkdir /app
RUN mkdir /app/static
RUN mkdir /app/images
WORKDIR /app
COPY requirements.txt /app/
RUN pip install -r requirements.txt
COPY ./bookwyrm /app
COPY ./celerywyrm /app

# crontab
COPY ./db_backup.sh /app
RUN apt-get update && apt-get -y install cron
COPY db-backups-cron /etc/cron.d/db-backups-cron
RUN chmod 0644 /etc/cron.d/db-backups-cron
RUN crontab /etc/cron.d/db-backups-cron
RUN touch /var/log/cron.log
CMD cron && tail -f /var/log/cron.log
