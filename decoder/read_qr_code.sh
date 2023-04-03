#!/bin/sh

set -e

TMPFILE=$(mktemp -t qr-XXXXXX)

trap "rm -f ${TMPFILE}" EXIT

cat - > $TMPFILE

zbarimg --raw -q $TMPFILE || (convert $TMPFILE -resize 50% png:- | zbarimg --raw -q :-)
