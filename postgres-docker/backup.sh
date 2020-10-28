#!/bin/bash
filename=backup__$(date +%F)
pg_dump -U fedireads  > /backups/$filename.sql
