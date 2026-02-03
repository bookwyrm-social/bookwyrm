#!/bin/bash
while true; do
    sleep 1d
    nginx -t && nginx -s reload
done &
