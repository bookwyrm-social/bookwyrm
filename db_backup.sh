#!/bin/bash
filename=backup__$(date +%F)
pg_dump -U fedireads | gzip > $filename.gz
