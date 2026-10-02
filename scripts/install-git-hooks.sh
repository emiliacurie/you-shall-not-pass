#!/usr/bin/env bash
# No implicit global install. Pass --repo /path or --global explicitly.
set -eu
exec python3 "$(dirname "$0")/install.py" "$@"
