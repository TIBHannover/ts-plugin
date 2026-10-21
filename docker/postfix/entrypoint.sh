#!/bin/sh
set -eu

: "${POSTFIX_HOSTNAME:?Set POSTFIX_HOSTNAME to the production mail hostname}"
postconf -e "myhostname = $POSTFIX_HOSTNAME"
postconf -e 'myorigin = $myhostname'

mkdir -p /var/spool/postfix/etc
cp /etc/resolv.conf /etc/hosts /etc/services /var/spool/postfix/etc/
mkdir -p /var/spool/postfix/etc/ssl/certs
cp /etc/ssl/certs/ca-certificates.crt /var/spool/postfix/etc/ssl/certs/
newaliases
postfix check
exec postfix start-fg
