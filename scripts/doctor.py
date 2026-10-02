#!/usr/bin/env python3
"""Read-only installation checks plus disposable adapter probes; no claim of live activation."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import harness


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', default='.')
    args = parser.parse_args()
    report = {'policy_valid': False, 'git_hooks_configured_here': False,
              'adapter_probes': {}, 'host_runtime_verified': False,
              'note': 'Probes test responses, not whether your running agent loaded its hooks. Run the live smoke test in setup.md.'}
    try:
        policy = harness.load_policy()
        report['policy_valid'] = True
        expected = (harness.ROOT / 'scripts/git-hooks').resolve()
        raw = harness.git(args.repo, 'config', '--path', '--get', 'core.hooksPath', required=False)
        repo = harness.git(args.repo, 'rev-parse', '--show-toplevel', required=False)
        report['in_repository'] = bool(repo)
        if raw and repo:
            report['git_hooks_configured_here'] = (Path(repo) / raw).resolve() == expected
        report['git_hook_files_executable'] = all(os.access(expected / n, os.X_OK) for n in ['pre-commit', 'pre-push'])
        if repo:
            try:
                _, branch, protected = harness.state(args.repo, policy)
                report['base_branch_resolved'] = True
                report['current_branch_protected'] = not branch or branch in protected
            except harness.GuardError:
                report['base_branch_resolved'] = False
        with tempfile.TemporaryDirectory(prefix='personal-harness-doctor-') as folder:
            env = os.environ.copy()
            env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM='1')
            subprocess.run(['git', 'init', '-q', '--initial-branch=main', folder], env=env, check=True)
            for host in ['claude', 'codex']:
                values = []
                for cmd in ['git status --short', 'git push origin main', 'git restore -- file.txt']:
                    payload = {'tool_name': 'Bash', 'cwd': folder, 'tool_input': {'command': cmd}}
                    p = subprocess.run([sys.executable, str(harness.ROOT/'scripts/harness.py'), 'hook', '--host', host], input=json.dumps(payload), text=True, capture_output=True)
                    value = json.loads(p.stdout) if p.returncode == 0 else {}
                    values.append(value.get('hookSpecificOutput', {}).get('permissionDecision', 'no_override'))
                report['adapter_probes'][host] = values
            report['default_policy_probes_pass'] = report['adapter_probes'] == {'claude': ['no_override', 'deny', 'ask'], 'codex': ['no_override', 'deny', 'deny']}
        print(json.dumps(report, indent=2))
        return 0 if report['default_policy_probes_pass'] else 1
    except Exception:
        report['error'] = 'Checks could not complete. Install requirements and validate the policy. No protection is claimed.'
        print(json.dumps(report, indent=2))
        return 1


if __name__ == '__main__':
    sys.exit(main())
