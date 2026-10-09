# Validation of this revision

## 2026-10-09 update: default deny for loss of work, escudo mod

- Real installation on one Mac (global Git hooks, Claude Code 2.1.295 hook). Live test in
  a disposable repo with a local bare remote: branch creation passed; push to main,
  `git restore` and `git reset --hard` were denied; the remote and the file were unchanged.
- Finding: with `require_scoped_approval`, Claude Code's auto mode approved the `ask` for
  `git restore` without prompting and the unsaved line was lost. The default policy now
  denies both loss-of-work actions.
- 29 unittest methods pass: fixtures still run under an explicit approval policy, plus
  tests for the new default deny and for Claude still asking under the approval policy.
- Escudo mod: 12 tests pass; live blocks produced the Spanish toast and history entries.
- Not verified: a person approving a Claude prompt in a non-auto mode, Codex after the
  change, other machines.

## 2026-10-02

All tests use disposable repositories, local bare remotes and synthetic
credentials. No live team repository or global hook configuration was changed.

- Policy validation and Codex skill frontmatter validation passed.
- 27 unittest methods passed, including 69 structured command cases in `cases.json`.
- Friction fixes: multi-line and heredoc commit messages, read-only chains with one
  change, `checkout` of an existing branch, and `your_...` placeholders are allowed.
  Regression cases confirm comment and early-heredoc-end tricks and chains of two
  changes are still refused.
- Actual Git hook tests verify a working-branch commit and push succeed, shared-branch
  commits/pushes are blocked, force updates and remote deletion are blocked, and existing
  repository hooks still run.
- Staged-content tests cover a credential in an ordinary source file, a staged secret
  hidden by a later clean working-file edit, private environment filenames, empty
  examples, and an unsafe example file. Matched secret values are not printed.
- Regression cases cover command substitutions, command chains, environment overrides,
  alternate directories, abbreviated destructive flags, default-branch discovery,
  default remote selection, dry-run negation, and denial before approval exceptions.
- Invalid schema values and malformed hook inputs are refused. Installer tests verify
  explicit scope is required and an existing hooksPath is not silently replaced.
- Shell entry points pass syntax checks.
- The friction fixes were not covered by the host smoke tests below; see the agent
  runs in the findings report.

## Live host smoke tests

The actual PreToolUse protocol was exercised through an auditing shim invoking the
same `harness.py hook --host ...` entry point. Hook responses were captured and actual
repository state was checked. See `host-smoke-results.json`.

| Host | Read status / create working branch | Protected push | Restore unsaved test file |
|---|---|---|---|
| Codex CLI 0.153.1 | Succeeded | Denied; remote main unchanged | Denied; content preserved |
| Claude Code 2.1.287 | Succeeded | Denied; remote main unchanged | Adapter returned ask; unattended host denied the unanswered prompt; content preserved |

Codex used a sandbox writable only in its disposable test area. The test vetted its
hook command and used the documented one-run hook-trust flag; it did not trust or
install hooks globally. Claude exposed only Bash with narrow allowed command patterns,
used dontAsk with permission-prompts none, and did not bypass permission checks.

These smoke tests do not verify a person approving a Claude prompt, a trusted approval
store, every host permission mode, a GUI session, Windows, other agents, or all crash /
timeout / untrusted-hook paths. Codex intentionally has no automatic cleanup approval
mechanism in this revision. Full installation's dependency download and global activation
were not performed on this user's machine. Local policy checks cannot certify arbitrary
shell programs or server branch protections.

An independent reviewer demonstrated additional edge cases; those were corrected and
added to regression tests. The final independent follow-up hit an account usage error;
the final complete local suite passed. Do not confuse these implementation tests with
the older guidance-only behavior comparison or claim a statistical reliability rate.

To rerun:

```sh
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python scripts/harness.py validate
.venv/bin/python scripts/doctor.py --repo /path/to/disposable/repo
```
