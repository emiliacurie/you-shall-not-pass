# Install, verify, and maintain the local checks

Editing the skill is not installing protection. Review the scope of installation and
reuse any explicit authorization already given for that scope. Do not silently change
global settings when only a project update was requested.

This version supports macOS/Linux shell entry points, Python 3.9+, Git, and `jsonschema`
from `requirements.txt`. Windows shell entry points and other agents are unverified.

## 1. Make the workflow discoverable

Place the skill in the agent's skill directory. Merge `rules-snippet.md` into the
repository's `AGENTS.md` for Codex, or `CLAUDE.md` for Claude. Preserve existing rules.
The snippet activates the workflow; it does not activate the executable checks.

## 2. Validate before activation

From the skill directory, create a dedicated environment and run:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scripts/harness.py validate
.venv/bin/python -m unittest discover -s tests -v
```

Validation rejects missing settings, unsupported choices and unknown fields. If the
policy is invalid or a required dependency is unavailable, fix setup before claiming
protection. The schema cannot verify the meaning of a Git operation by itself.

Configure team-specific protected branches in `policy.json`. By default, the evaluator
also reads each remote's cached default branch. During initial setup, check the hosting
service's actual default, then use `git remote set-head origin -a` when network access
is available, or set the verified branch explicitly with `git remote set-head origin
<branch>`. Do this before agent-hook activation. Repeat for other remotes. If working
offline without cached defaults, explicitly list all agreed base branches and set
`include_default` to false only as a deliberate configuration choice. A missing cache
otherwise blocks supported Git mutations rather than guessing.

## 3. Install Git hooks for the intended scope

Prefer a repository-specific installation:

```sh
python3 scripts/install.py --repo /absolute/path/to/project
```

The installer copies the package to `~/.you-shall-not-pass`, installs its Python dependency
in that directory's `.venv`, validates the policy, and sets only the selected repository's
`core.hooksPath`. It stops if a different effective hooksPath or an existing destination
needs migration. Nothing is silently replaced. Dependency installation needs network
access. A failed installation may leave a partial destination for inspection; it does
not activate agent hooks.

For a different destination, add `--destination /absolute/path/to/install`. For an
explicitly requested global installation, use `--global` instead of `--repo`. The
compatibility script `scripts/install-git-hooks.sh` accepts the same options and no
longer defaults to a global change.

Existing ordinary repository pre-commit and pre-push hooks are chained. A custom hook
manager needs deliberate integration, not a second hooksPath that silently replaces it.
Keep installed code and policy outside the agent's writable workspace where practical.
Local ownership still does not make them a server-side security boundary.

Undo only the scope you installed: `git -C /project config --unset core.hooksPath` for
a local installation, or `git config --global --unset core.hooksPath` for a global one.
Inspect existing configuration first; do not remove someone else's hook configuration.

## 4. Activate the correct agent adapter

The installer generates absolute-path snippets in:

- `~/.you-shall-not-pass/integrations/claude.generated.json`
- `~/.you-shall-not-pass/integrations/codex.generated.json`

Merge the relevant `hooks` entries into the existing configuration without replacing
other hooks. Example snippets are also included in `integrations/`; adjust their
installation paths if needed.

**Claude:** use `~/.claude/settings.json` or a deliberately scoped project setting.
With the default policy the adapter returns `deny` for blocks and for destructive
operations. It returns `ask` only if the policy sets `require_scoped_approval`; the host's
permission mode then decides, and auto mode approved an ask without prompting in our
test. Do not use a permissions-bypass mode as evidence that approval protection works.
Optionally, install the [escudo mod](escudo.md) to see this protection inside Claude Code.

**Codex:** use `~/.codex/hooks.json` or the project's `.codex/hooks.json`. Review and
trust new/changed hooks using `/hooks` in the CLI. Hooks needing review may be skipped;
verify activation. The adapter returns `deny` for both blocked and approval-required
operations. Current PreToolUse does not support `ask`: do not copy Claude's response
format for approval requests into Codex. Unsupported ask responses can fail and allow
the tool call to continue.

### When the person really wants to discard work

The guard blocks it, so the person runs it. This applies to Claude and Codex alike.

1. The agent lists the exact files or branches and what each would lose, and gives the
   single command that does it, for example `git -C /path/to/repo restore -- notes.txt`.
2. The person reads the list. If it's right, they run the command themselves:
   - In Claude Code: type `!`, paste the command without the `!`, press Enter.
   - In Codex or anywhere else: paste it into a normal terminal.
3. The agent checks the result with a read-only command such as `git status`.

Commands run this way don't pass through the agent hook, and the Git hooks only check
commits and pushes, so the person's command goes through. Do not disable the hook, emit
an agent-created approval token, or reroute the action through another tool. This
manual path applies only to destructive operations, not ordinary edits and uploads.

**Migration:** older installations using `agent-guard.sh` without a host argument will
block with migration guidance. Point Claude to `scripts/claude-guard.sh` and Codex to
`scripts/codex-guard.sh`. The old generic mappings for Cursor, Gemini, Copilot and
Windsurf are not certified for this version. Do not claim they are active protections.

## 5. Verify the installation

```sh
~/.you-shall-not-pass/.venv/bin/python ~/.you-shall-not-pass/scripts/doctor.py --repo /project
```

The diagnostic checks policy validity, effective Git hooksPath, executable entry points,
and adapter responses in a disposable repository. `host_runtime_verified` stays false:
these probes cannot establish what an existing agent session has loaded. A customized
policy can intentionally differ from the diagnostic's default-policy expectations;
review its reported decisions rather than changing policy merely to make a probe pass.

For a live smoke test, use a new temporary repository and a local bare remote. Do not
use the team repository. Have an agent attempt these commands separately:

1. Read status and create a working branch: these should complete.
2. Push a local feature commit to `HEAD:main`: the guard must deny it, and the bare
   remote's main ref must remain unchanged.
3. Restore a file containing unsaved test content: both hosts must deny it with the
   default policy, and the file must remain unchanged.

Inspect host hook events as well as resulting refs/files. A model declining a command
before trying it does not prove a hook blocked it. Also exercise a missing dependency,
invalid policy, untrusted hook, and timeout before claiming host failure behavior.

## Scope of claims

Read `references/coverage.md` and `tests/VALIDATION.md`. Report the exact tool/version,
which layer was tested, and what remains unverified. Server branch rules, required
reviews, CI and provider spending controls need separate setup and verification.

Sources: [Codex hooks](https://learn.chatgpt.com/docs/hooks),
[Claude hooks](https://code.claude.com/docs/en/hooks),
[Git hooks](https://git-scm.com/docs/githooks).
