#!/bin/bash
filename=backup__$(date +%F)
pg_dump -U bookwyrm  > /backups/$filename.sql
