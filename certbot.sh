#!/usr/bin/env bash
source .env;

if [ "$CERTBOT_INIT" = "true" ]
then
    certonly \
    --webroot \
    --webroot-path=/var/www/certbot \
    --email ${EMAIL} \
    --agree-tos \
    --no-eff-email \
    -d ${DOMAIN} \
    -d www.${DOMAIN}
else
    renew \
    --webroot \
    --webroot-path \
    /var/www/certbot
fi
