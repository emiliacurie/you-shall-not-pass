#!/usr/bin/env bash
set -eu
root="$(cd "$(dirname "$0")/.." && pwd)"
python="$root/.venv/bin/python"
if [[ ! -x "$python" ]]; then
  python=$(command -v python3) || { echo "Blocked by You Shall Not Pass: Python is missing." >&2; exit 2; }
fi
exec "$python" "$root/scripts/harness.py" hook --host claude
