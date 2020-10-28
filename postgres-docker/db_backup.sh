#!/bin/bash
filename=backup__$(date +%F)
pg_dump -U fedireads  > $filename.sql
