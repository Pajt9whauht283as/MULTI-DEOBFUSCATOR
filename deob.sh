#!/usr/bin/env bash
# shortcut for the Python entrypoint, so `deob run file.lua` works on unix
set -euo pipefail
exec python3 "$(dirname "$0")/deob.py" "$@"
