#!/usr/bin/env bash
# Tail webhook catcher logs, extracting notification payloads.

set -e

cd "$(dirname "$0")/.."

docker compose logs -f --no-log-prefix webhook 2>&1 \
    | grep --line-buffered '^{' \
    | jq --unbuffered '.json | {title, message, data}'
