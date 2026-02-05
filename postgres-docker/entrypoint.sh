#!/bin/sh

env >>/etc/environment

echo "$@"
exec "$@"
