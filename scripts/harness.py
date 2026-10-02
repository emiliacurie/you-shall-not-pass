#!/usr/bin/env python3
"""Local guardrails, not an arbitrary-shell security boundary. See references/coverage.md."""
import argparse
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent


class GuardError(Exception):
    pass


def git(cwd, *args, required=True):
    env = os.environ.copy()
    # Inspection must not invoke pagers, editors, external diffs or lazy network fetches.
    env.update(GIT_PAGER='cat', GIT_TERMINAL_PROMPT='0', GIT_NO_LAZY_FETCH='1')
    p = subprocess.run(['git', '-C', str(cwd), *args], capture_output=True, env=env, timeout=15)
    if p.returncode and required:
        raise GuardError('Could not inspect Git state. No action was authorized.')
    return p.stdout.decode('utf-8', errors='replace').rstrip('\n') if not p.returncode else None


def load_policy():
    try:
        from jsonschema import Draft202012Validator
        schema = json.loads((ROOT / 'policy.schema.json').read_text())
        value = json.loads((ROOT / 'policy.json').read_text())
        Draft202012Validator.check_schema(schema)
        errors = list(Draft202012Validator(schema).iter_errors(value))
        if errors:
            # Do not print user-supplied values, which might contain secrets.
            raise GuardError('Invalid policy at ' + '.'.join(map(str, errors[0].absolute_path)))
        for branch in value['protected_branches']['additional']:
            p = subprocess.run(['git', 'check-ref-format', 'refs/heads/' + branch], capture_output=True)
            if p.returncode:
                raise GuardError('Invalid protected branch name in policy.')
        return value
    except GuardError:
        raise
    except Exception:
        raise GuardError('Policy validation unavailable. Install requirements and check policy.json.')


def state(cwd, policy):
    root = git(cwd, 'rev-parse', '--show-toplevel', required=False)
    if root is None:
        return None, '', set(policy['protected_branches']['additional'])
    protected = set(policy['protected_branches']['additional'])
    if policy['protected_branches']['include_default']:
        remotes = git(cwd, 'remote').splitlines()
        for remote in remotes:
            ref = git(cwd, 'symbolic-ref', '--short', 'refs/remotes/' + remote + '/HEAD', required=False)
            if ref:
                protected.add(ref[len(remote) + 1:])
            else:
                # Do not guess a server default when its cached symbolic ref is missing.
                raise GuardError('Default branch is unknown. Set the remote HEAD or explicitly configure the base branch; see setup.md.')
    return root, git(cwd, 'branch', '--show-current'), protected


def decision(policy, action, reason):
    return {'decision': policy['actions'][action], 'rule': action, 'reason': reason}


def deny(reason, rule='unsupported_command'):
    return {'decision': 'deny', 'rule': rule, 'reason': reason}


def allow():
    return {'decision': 'allow', 'rule': 'none', 'reason': ''}


def env_file(name):
    return any(p == '.env' or p.startswith('.env.') for p in Path(name).parts) and not name.endswith(('.example', '.sample', '.template'))


def detected_secret(content):
    # Deliberately small set; not a replacement for a provider-grade secret scanner.
    patterns = [r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
                r'\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{30,}|AKIA[A-Z0-9]{16}|sk-(?:proj-)?[A-Za-z0-9_-]{20,})\b']
    if any(re.search(p, content) for p in patterns):
        return True
    assignment = r'''(?im)["']?(?:[A-Z0-9_]*(?:API_KEY|SECRET_KEY|ACCESS_TOKEN|AUTH_TOKEN|PASSWORD))["']?[ \t]*[:=][ \t]*["']?([^\s"',;\}\)]+)'''
    for value in re.findall(assignment, content):
        if not placeholder(value) and not value.startswith(('$', '<', 'process.env.', 'os.environ', 'os.getenv', 'getenv(')):
            return True
    return False


def placeholder(value):
    v = value.lower()
    return (v in {'', 'changeme', 'change_me', 'replace_me', 'example', 'placeholder', 'null', 'none', 'todo'}
            or re.match(r'^(?:your|my)[-_]', v) is not None
            or re.fullmatch(r'[x*.]+', v) is not None)


def staged_check(cwd, policy):
    # Use the index, never the working file: a staged secret can differ from the worktree.
    names = git(cwd, 'diff', '--cached', '--name-only', '--diff-filter=ACMR', '-z')
    for name in names.split('\0'):
        if not name:
            continue
        if env_file(name) and policy['actions']['commit_env_file'] == 'deny':
            return decision(policy, 'commit_env_file', 'An environment file is staged. Keep it local and share a placeholder example.')
        text = git(cwd, 'show', ':' + name)
        if policy['actions']['commit_detected_secret'] == 'deny' and detected_secret(text):
            return decision(policy, 'commit_detected_secret', 'Staged content resembles a credential. Remove it from the index; no credential value is logged.')
    return allow()


# A quoted heredoc delimiter disables expansion, so the body is literal text.
HEREDOC_MESSAGE = re.compile(r'''"\$\(cat <<-?(['"])(\w+)\1\n(.*?)\n\2\n\s*\)"''', re.S)
SAFE_READERS = {'cat', 'head', 'tail', 'grep', 'ls', 'pwd', 'echo', 'printf', 'wc', 'uniq', 'cut', 'true'}
READ_ONLY_FORMS = {'branch', 'remote', 'symbolic-ref', 'config'}


def heredoc_literal(match):
    # The shell ends the heredoc at the first delimiter line; anything after it would run.
    if re.search(r'(?m)^' + re.escape(match.group(2)) + '$', match.group(3)):
        return match.group(0)
    return shlex.quote(match.group(3))


def unquoted_newlines_to_separators(command):
    out, quote, i = [], None, 0
    while i < len(command):
        ch = command[i]
        if quote == "'":
            quote = None if ch == "'" else quote
        elif ch == '\\' and i + 1 < len(command):
            out.append(' ' if quote is None and command[i + 1] == '\n' else ch + command[i + 1])
            i += 2
            continue
        elif quote == '"':
            quote = None if ch == '"' else quote
        elif ch in '\'"':
            quote = ch
        elif ch == '#' and (i == 0 or command[i - 1] in ' \t\n;&|('):
            while i < len(command) and command[i] != '\n':
                i += 1
            continue
        elif ch == '\n':
            ch = ' ; '
        out.append(ch)
        i += 1
    return ''.join(out)


def chain_check(segments, cwd, policy):
    # Read-only steps cannot change the state a single change is checked against.
    changes = []
    for part in segments:
        executable = Path(part[0]).name
        if executable == 'git':
            result = command_check(shlex.join(part), cwd, policy)
            if result['decision'] != 'allow':
                return result
            if len(part) < 2 or not (part[1] in READ_ONLY_GIT or part[1] in READ_ONLY_FORMS):
                changes.append(result)
        elif executable in SAFE_READERS:
            continue
        else:
            result = command_check(shlex.join(part), cwd, policy)
            if result['decision'] != 'allow' or executable in {'rm', 'rmdir'}:
                return result
            return deny('Run Git commands separately from other programs so each is checked at execution time.')
    if len(changes) > 1:
        return deny('Run each Git change as its own command so it is checked against the state at that moment. Read-only commands can be grouped.')
    return allow()


READ_ONLY_GIT = {'status', 'diff', 'log', 'show', 'rev-parse', 'rev-list', 'ls-files', 'ls-tree', 'check-ignore', 'check-ref-format', 'merge-base', 'for-each-ref', 'version', 'help', 'ls-remote'}
SEPARATORS = {';', '&&', '||', '|', '&', '(', ')', '<', '>', '>>', '<<', '<<<', '\n'}


def command_check(command, cwd, policy):
    # shlex handles quoting for simple invocations. Compound shell programs are not simulated.
    if not isinstance(command, str) or not command.strip():
        return deny('Missing command input.', 'invalid_input')
    command = HEREDOC_MESSAGE.sub(heredoc_literal, command)
    command = unquoted_newlines_to_separators(command).strip().rstrip(';').strip()
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=';&|()<>' )
        lexer.whitespace = ' \t\r'
        lexer.whitespace_split = True
        lexer.commenters = '#'
        words = list(lexer)
    except ValueError:
        return deny('Cannot parse this command. Run a simple command separately.')
    if not words:
        return allow()
    # Ignore harmless quoted examples. This is command classification, not substring matching.
    executable = Path(words[0]).name
    if '$(' in command or '`' in command:
        return deny('Shell substitutions cannot be checked as a single operation. Run the underlying command directly.')
    if executable in {'echo', 'printf'} and not any(w in SEPARATORS for w in words):
        return allow()
    if re.match(r'^[A-Za-z_][A-Za-z0-9_]*=', words[0]):
        return deny('Environment-prefixed commands are outside the supported subset; they can override Git checks.')
    if executable in {'sh', 'bash', 'zsh', 'env', 'sudo', 'eval', 'command', 'xargs'}:
        return deny('Wrapper commands cannot be checked reliably. Run the underlying command directly.')
    # Git commands or a recognized destructive command within a chain must run separately.
    relevant = any(Path(w).name in {'git', 'rm', 'rmdir'} for w in words)
    if relevant and any(w in {';', '&&', '||', '|'} for w in words) and not any(w in {'&', '<', '>', '>>', '<<', '<<<', '(', ')'} for w in words) and '$' not in command and '`' not in command:
        segments, segment = [], []
        for word in words:
            if word in {';', '&&', '||', '|'}:
                if segment:
                    segments.append(segment)
                segment = []
            else:
                segment.append(word)
        if segment:
            segments.append(segment)
        if len(segments) > 1:
            return chain_check(segments, cwd, policy)
    if relevant and (any(w in SEPARATORS for w in words) or '$(' in command or '`' in command):
        return deny('Run Git and destructive commands separately so each is checked against the state at execution time.')
    if executable in {'rm', 'rmdir'}:
        return decision(policy, 'discard_unsaved_work', 'Deletion requires approval for the exact command and affected files. A backup is not approval.')
    if executable != 'git':
        return allow()  # Other interpreters/scripts are explicitly outside this guard's coverage.
    args = words[1:]
    cwd = Path(cwd)
    while args and args[0].startswith('-'):
        flag = args.pop(0)
        if flag == '-C' and args:
            cwd = (cwd / args.pop(0)).resolve()
        elif flag.startswith('-C') and len(flag) > 2:
            cwd = (cwd / flag[2:]).resolve()
        elif flag in {'--no-pager', '--no-optional-locks'}:
            pass
        elif flag in {'--version', '--help'}:
            return allow()
        else:
            return deny('Git global overrides are not supported by this guard. Run without the override.')
    if not args:
        return allow()
    op, rest = args[0], args[1:]
    if op == 'symbolic-ref' and len([x for x in rest if not x.startswith('-')]) == 1 and all(not x.startswith('-') or x in {'--short', '-q', '--quiet', '--no-recurse'} for x in rest):
        return allow()
    if op == 'config' and (rest[:1] in [['--get'], ['--get-all'], ['--get-regexp'], ['--list']] or (len(rest) == 1 and not rest[0].startswith('-'))):
        return allow()
    if op in READ_ONLY_GIT:
        if any(x in {'--output', '--ext-diff', '--textconv', '--exec-path'} or x.startswith('--output=') for x in rest):
            return deny('This inspection command has side effects not covered by the guard.')
        return allow()
    root, branch, protected = state(cwd, policy)
    if not root:
        return deny('Run this Git action inside a repository.')
    if op in {'commit', 'push', 'merge', 'rebase'} and ('--no-verify' in rest or (op in {'commit','push'} and '-n' in rest)):
        result = decision(policy, 'skip_checks', 'Skipping checks is disabled.')
        if result['decision'] != 'allow':
            return result
        rest = [x for x in rest if x not in {'--no-verify', '-n'}]
    if op == 'commit':
        # Keep a small explicit grammar; short option clusters can hide -n or -a.
        amend = False
        index = 0
        while index < len(rest):
            flag = rest[index]
            if flag in {'-m', '--message'} and index + 1 < len(rest):
                index += 2
            elif flag.startswith('--message=') or flag in {'--verbose', '-v', '--quiet', '-q', '--allow-empty', '--dry-run'}:
                index += 1
            elif flag == '--amend':
                amend = True
                index += 1
            else:
                return deny('Commit only the inspected index using -m or --message. Combined flags, path arguments and automatic staging are unsupported.')
        if any(x in {'-a', '--all', '--include', '-i', '--only', '-o'} for x in rest) or '--' in rest:
            return deny('Stage named files first, then commit the inspected index without automatic staging or path arguments.')
        if not branch or branch in protected:
            result = decision(policy, 'commit_to_protected_branch', 'Create a working branch before committing on a shared or detached branch.')
            if result['decision'] != 'allow':
                return result
        result = staged_check(cwd, policy)
        if result['decision'] != 'allow':
            return result
        if amend:
            return decision(policy, 'rewrite_history', 'Amending rewrites the last commit. Approve the specific change first.')
        return allow()
    if op == 'merge':
        if any(x.startswith('-') and x not in {'--ff-only', '--no-ff', '--ff', '--no-edit', '--no-commit', '--squash', '--quiet', '-q', '--abort', '--quit'} for x in rest):
            return deny('Use explicit supported merge flags; abbreviated and override flags are not supported.')
        if '--abort' in rest or '--quit' in rest:
            return decision(policy, 'discard_unsaved_work', 'Ending this merge can alter in-progress work. Approve the affected work first.')
        if branch in protected or not branch:
            return decision(policy, 'merge_into_protected_branch', 'Changes reach a shared branch through a reviewed pull request, including fast-forward merges.')
        return allow()
    if op == 'push':
        if any(x.startswith(('--force', '--mirror')) or x == '-f' or x.startswith('+') for x in rest):
            result = decision(policy, 'force_push', 'Force pushes can replace shared history.')
            if result['decision'] != 'allow':
                return result
            rest = [x for x in rest if not x.startswith(('--force', '--mirror')) and x != '-f']
            rest = [x[1:] if x.startswith('+') else x for x in rest]
        if any(x in {'--delete', '-d'} or x.startswith(':') for x in rest):
            result = decision(policy, 'delete_remote_branch', 'Remote branch deletion is disabled.')
            if result['decision'] != 'allow':
                return result
            rest = [x for x in rest if x not in {'--delete', '-d'}]
        # Explicit remote and refs avoid implicit push.default, push refspecs and --all.
        positional = [x for x in rest if x not in {'-u', '--set-upstream'}]
        if any(x.startswith('-') for x in positional) or len(positional) < 2:
            return deny('Use an explicit remote and branch: git push -u origin <working-branch>.')
        for ref in positional[1:]:
            target = ref.split(':')[-1].removeprefix('refs/heads/')
            if target == 'HEAD':
                target = branch
            if '*' in target or not target:
                return deny('Wildcard or empty push destinations are not supported.')
            if target in protected:
                result = decision(policy, 'push_to_protected_branch', 'Push a working branch and open a pull request instead of updating a shared branch.')
                if result['decision'] != 'allow':
                    return result
        return allow()
    if op in {'restore', 'reset', 'clean'} or (op == 'checkout' and ('--' in rest or not rest or any(x in {'-f', '--force'} for x in rest))):
        if op == 'clean' and ('-n' in rest or '--dry-run' in rest) and all(not x.startswith('-') or x in {'-n', '--dry-run', '-d', '-x', '-X', '--'} for x in rest):
            return allow()
        return decision(policy, 'discard_unsaved_work', 'This can discard work. Approval must cover the affected files and operation; a backup is not approval.')
    if op == 'rebase' or (op == 'stash' and (not rest or rest[0] in {'drop', 'clear', 'pop', 'push', 'save', 'apply'})) or (op == 'branch' and any(x in {'-D', '-d', '--delete', '-f', '--force'} for x in rest)):
        return decision(policy, 'rewrite_history', 'This changes history, branches or saved work. Approve the specific operation first.')
    if op in {'switch', 'checkout'}:
        if any(x in {'-C', '-B', '--force-create', '-f', '--force', '--discard-changes', '-m', '--merge'} for x in rest):
            return decision(policy, 'discard_unsaved_work', 'This branch change can overwrite existing work.')
        if op == 'checkout' and rest[:1] == ['-b'] and len(rest) in {2, 3}:
            rest = ['-c'] + rest[1:]
        elif op == 'checkout' and not (len(rest) == 1 and git(cwd, 'rev-parse', '--verify', '--quiet', 'refs/heads/' + rest[0], required=False)):
            return deny('Use git switch for branches; git checkout can also overwrite files.')
        branch_args = rest[1:] if rest[:1] in [['-c'], ['--create']] else rest
        if not branch_args or len(branch_args) > (2 if rest[:1] in [['-c'], ['--create']] else 1) or any(x.startswith('-') for x in branch_args):
            return deny('Use git switch <branch> or git switch -c <new-branch> [base]. Combined and override flags are unsupported.')
        return allow()
    if op == 'add':
        for name in rest:
            if env_file(name):
                return decision(policy, 'commit_env_file', 'Keep environment files out of the index.')
        return allow()  # The real staged content is checked by pre-commit.
    if op == 'fetch':
        allowed_flags = {'--prune', '--tags', '--no-tags', '--quiet', '-q'}
        if any(x.startswith('-') and x not in allowed_flags for x in rest):
            return deny('Use git fetch <named-remote> without refspec or override flags.')
        names = [x for x in rest if x not in allowed_flags]
        if len(names) != 1:
            return deny('Use exactly one explicit named remote; implicit remotes and fetch refspecs are unsupported.')
        remote = names[0]
        if remote not in git(cwd, 'remote').splitlines():
            return deny('Fetch must use a configured named remote.')
        specs = git(cwd, 'config', '--get-all', 'remote.' + remote + '.fetch', required=False)
        if not specs or any(':' not in spec or not spec.split(':', 1)[1].startswith('refs/remotes/') for spec in specs.splitlines()):
            return deny('Remote fetch mappings are not confined to remote-tracking references.')
        return allow()
    if op == 'pull':
        if branch in protected or not branch:
            return deny('Fetch for inspection. Updating the shared branch locally requires a separately reviewed workflow.')
        if '--ff-only' not in rest or any(x.startswith('-') and x not in {'--ff-only', '--quiet', '-q'} for x in rest):
            return deny('Use pull --ff-only without override or abbreviated flags.')
        names = [x for x in rest if not x.startswith('-')]
        if len(names) != 1 or names[0] not in git(cwd, 'remote').splitlines():
            return deny('Pull supports a named remote only; explicit refspecs are not supported.')
        result = command_check('git fetch ' + shlex.quote(names[0]), cwd, policy)
        return result
    listing = {'--show-current', '--all', '--remotes', '--verbose', '--no-color'}
    if op == 'branch' and (all(x in listing or re.fullmatch(r'-[arv]+', x) for x in rest) or (rest[:1] == ['--list'] and all(not x.startswith('-') for x in rest[1:]))):
        return allow()
    if op == 'remote' and (not rest or rest == ['-v'] or rest[:1] == ['get-url']):
        return allow()
    return deny('This Git operation is outside the supported subset. Inspect it with a developer rather than changing command spelling.')


def tool_check(payload, policy):
    if not isinstance(payload, dict) or not isinstance(payload.get('cwd'), str) or not isinstance(payload.get('tool_input'), dict):
        return deny('Missing hook context; no action was authorized.', 'invalid_input')
    name, data, cwd = payload.get('tool_name'), payload['tool_input'], payload['cwd']
    if name in {'Bash', 'exec_command'}:
        if 'workdir' in data:
            if not isinstance(data['workdir'], str):
                return deny('Invalid command working directory.', 'invalid_input')
            cwd = str((Path(cwd) / data['workdir']).resolve())
        return command_check(data.get('command', data.get('cmd')), cwd, policy)
    if name in {'Edit', 'Write', 'MultiEdit', 'NotebookEdit', 'apply_patch'}:
        paths = []
        if name == 'apply_patch':
            patch = data.get('command', '')
            paths = re.findall(r'^\*\*\* (?:Add File|Update File|Delete File|Move to): (.+)$', patch, re.M)
        else:
            paths = [data.get('file_path') or data.get('notebook_path')]
        if not paths or any(not isinstance(x, str) for x in paths):
            return deny('Cannot determine the edited files.', 'invalid_input')
        for filename in paths:
            target = (Path(cwd) / filename).resolve()
            parent = target.parent
            while not parent.exists() and parent != parent.parent:
                parent = parent.parent
            root, branch, protected = state(parent, policy)
            if root and (branch in protected or not branch):
                result = decision(policy, 'edit_on_protected_branch', 'Create a working branch before editing shared-branch files.')
                if result['decision'] != 'allow':
                    return result
        return allow()
    return allow()


def hook_response(result, host):
    d = result['decision']
    if d == 'allow':
        return {}  # Do not override host permissions with a blanket allow.
    if d == 'require_scoped_approval':
        if host == 'claude':
            d = 'ask'
        else:
            d = 'deny'
            result = dict(result, reason=result['reason'] + ' Codex PreToolUse cannot ask. Stop and use a human-controlled terminal after reviewing the files; do not retry via another tool.')
    return {'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'permissionDecision': d, 'permissionDecisionReason': 'Personal harness: ' + result['reason']}}


def pre_commit(policy):
    _, branch, protected = state(Path.cwd(), policy)
    if not branch or branch in protected:
        result = decision(policy, 'commit_to_protected_branch', 'Create a working branch before committing.')
        if result['decision'] != 'allow':
            return result
    return staged_check(Path.cwd(), policy)


def pre_push(policy, text):
    _, _, protected = state(Path.cwd(), policy)
    for line in text.splitlines():
        fields = line.split()
        if len(fields) != 4:
            return deny('Malformed Git push input.', 'invalid_input')
        local_ref, local_sha, remote_ref, remote_sha = fields
        if remote_ref.removeprefix('refs/heads/') in protected:
            r = decision(policy, 'push_to_protected_branch', 'The actual destination is a protected branch.')
            if r['decision'] != 'allow':
                return r
        if set(local_sha) == {'0'}:
            r = decision(policy, 'delete_remote_branch', 'Deleting a remote ref is disabled.')
            if r['decision'] != 'allow':
                return r
            continue
        if set(remote_sha) != {'0'}:
            p = subprocess.run(['git', 'merge-base', '--is-ancestor', remote_sha, local_sha], capture_output=True)
            if p.returncode:
                r = decision(policy, 'force_push', 'This update is not proven to preserve remote history.')
                if r['decision'] != 'allow':
                    return r
    return allow()


def run_repo_hook(name, args, input_text=''):
    # Preserve ordinary repository hooks, including linked worktrees, without recursing.
    raw = git(Path.cwd(), 'rev-parse', '--git-common-dir')
    target = (Path(raw) / 'hooks' / name).resolve()
    own = (ROOT / 'scripts/git-hooks' / name).resolve()
    if target.exists() and target != own and os.access(target, os.X_OK):
        return subprocess.run([str(target), *args], input=input_text.encode()).returncode
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['validate', 'hook', 'pre-commit', 'pre-push'])
    parser.add_argument('--host', choices=['claude', 'codex'])
    parser.add_argument('hook_args', nargs='*')
    args = parser.parse_args()
    try:
        policy = load_policy()
        if args.mode == 'validate':
            print('Policy is valid (version 1).')
            return 0
        if args.mode == 'hook':
            if args.host is None:
                raise GuardError('Choose --host claude or --host codex.')
            result = tool_check(json.load(sys.stdin), policy)
            print(json.dumps(hook_response(result, args.host)))
            return 0
        text = sys.stdin.read() if args.mode == 'pre-push' else ''
        result = pre_commit(policy) if args.mode == 'pre-commit' else pre_push(policy, text)
        if result['decision'] != 'allow':
            print('Blocked by personal harness: ' + result['reason'], file=sys.stderr)
            return 1
        return run_repo_hook(args.mode, args.hook_args, text)
    except Exception:
        # Hook stderr must not disclose event contents, commands, credentials or raw parser errors.
        print('Blocked by personal harness: validation or inspection failed. Run the diagnostic; do not bypass this check.', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
