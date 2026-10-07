#!/bin/sh
set -eu
: "${API_UPSTREAM:=api:8000}"
: "${DNS_RESOLVER:=$(awk '/^nameserver/ {print $2; exit}' /etc/resolv.conf)}"
export API_UPSTREAM DNS_RESOLVER
envsubst '${API_UPSTREAM} ${DNS_RESOLVER}' < /etc/nginx/nginx.conf.template > /tmp/nginx.conf
exec nginx -c /tmp/nginx.conf -g 'daemon off;'
