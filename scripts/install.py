#!/usr/bin/env python3
"""Explicit installation only. Never edits agent settings or silently replaces Git hooks."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

SOURCE = Path(__file__).resolve().parent.parent


def main():
    p = argparse.ArgumentParser()
    scope = p.add_mutually_exclusive_group(required=True)
    scope.add_argument('--repo', type=Path, help='Configure hooks for this repository only')
    scope.add_argument('--global', dest='global_scope', action='store_true', help='Explicitly configure hooks for every repository')
    p.add_argument('--destination', type=Path, default=Path.home()/'.you-shall-not-pass')
    a = p.parse_args()
    dest = a.destination.expanduser().resolve()
    if a.repo:
        repo = a.repo.resolve()
        subprocess.run(['git', '-C', str(repo), 'rev-parse', '--show-toplevel'], check=True, stdout=subprocess.DEVNULL)
        prefix = ['git', '-C', str(repo), 'config']
    else:
        prefix = ['git', 'config', '--global']
    existing = subprocess.run(prefix + ['--get', 'core.hooksPath'], capture_output=True, text=True)
    hooks = dest/'scripts/git-hooks'
    if existing.returncode == 0 and existing.stdout.strip() != str(hooks):
        raise SystemExit('Existing hooksPath found. Installation stopped; combine hooks with a developer instead of replacing them.')
    if dest == SOURCE or dest in SOURCE.parents or SOURCE in dest.parents:
        raise SystemExit('Choose an installation folder separate from the source skill.')
    # Do not replace an installation policy or interpreter silently during an update.
    if dest.exists():
        raise SystemExit('Destination already exists. Review and migrate the existing installation before replacing it.')
    try:
        shutil.copytree(SOURCE, dest, ignore=shutil.ignore_patterns('.venv', '__pycache__', '*.pyc', 'tests'))
        subprocess.run([sys.executable, '-m', 'venv', str(dest/'.venv')], check=True)
        python = dest/'.venv/bin/python'
        subprocess.run([str(python), '-m', 'pip', 'install', '-r', str(dest/'requirements.txt')], check=True)
        subprocess.run([str(python), str(dest/'scripts/harness.py'), 'validate'], check=True)
        # This is the first configuration mutation, after all prerequisites succeed.
        subprocess.run(prefix + ['core.hooksPath', str(hooks)], check=True)
        for host in ['claude', 'codex']:
            command = str(dest / 'scripts' / (host + '-guard.sh'))
            import shlex
            snippet = {'hooks': {'PreToolUse': [{'matcher': 'Bash|Edit|Write|MultiEdit|NotebookEdit' if host == 'claude' else 'Bash|apply_patch', 'hooks': [{'type': 'command', 'command': shlex.quote(command)}]}]}}
            (dest/'integrations'/f'{host}.generated.json').write_text(json.dumps(snippet, indent=2)+'\n')
        print('Git hooks configured. Agent hooks are NOT activated. Merge the generated integration into your agent settings and run the live smoke test.')
    except Exception:
        print('Installation failed. Inspect the destination before retrying. Agent settings were not changed.', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
