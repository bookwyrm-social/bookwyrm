#!/bin/sh

env >>/etc/environment

echo "$(date --iso-8601=seconds) starting backup node"
exec "$@"
