#!/usr/bin/env bash
# Compatibility entry point: the host must be explicit; never guess an approval protocol.
set -eu
case "${1:-}" in
  --claude) exec "$(dirname "$0")/claude-guard.sh" ;;
  --codex) exec "$(dirname "$0")/codex-guard.sh" ;;
  *) echo "Blocked by You Shall Not Pass: use claude-guard.sh or codex-guard.sh; see references/setup.md." >&2; exit 2 ;;
esac
