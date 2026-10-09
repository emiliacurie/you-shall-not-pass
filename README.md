# You Shall Not Pass

![You Shall Not Pass: a guardrail for AI coding agents](docs/banner.jpg)

A guardrail for AI coding agents.

**What it does for you:** when you ask an AI coding agent to "fix the footer" or "upload
it", the agent works on its own branch and opens a pull request instead of changing the
team's shared branch. It also keeps secrets like `.env` out of commits and stops before
deleting unsaved work. It's tested on Claude Code and Codex. A developer installs it
once; after that it works in the background.

## What changes when you install it

The skill works on three levels. Some rules are locked: the agent can't break them, even
if you ask. Some protect work you haven't saved yet. The rest are habits the agent
follows because the skill tells it to, but nothing forces them.

**🔒 Always blocked.** Protected branches are `main`, `master`, `develop`, `production`,
`release` and the repo's default branch.

| The agent won't | Why |
|---|---|
| Save (commit), upload (push) or merge into a protected branch | Changes reach the team through a reviewed pull request |
| Edit files while you're on a protected branch | It moves to a working branch first |
| Force-push or delete a branch on GitHub | Both can erase other people's work |
| Skip checks (`--no-verify`) | The checks are the safety net |
| Commit `.env` or anything that looks like a password or key | Once uploaded, a secret stays in the history |

**✋ Protects unsaved work.** These can lose work, so they're blocked too. Asking
instead isn't safe by default: Claude Code's auto mode approves the question on its own.
If you really want to delete something, the agent lists what would be lost and gives
you one command. In Claude Code, type `!`, paste the command, and press Enter; in
Codex, paste it into a terminal.

| Action | Examples |
|---|---|
| Discard unsaved work | "start over", "clean this up", deleting files |
| Rewrite history | rebasing, editing the last commit, deleting a branch |

**📖 Habits it follows.** It creates its own branch for each task. When you say "upload
it", it pushes that branch and opens a pull request; it won't ask again for each step. It
saves only the files that belong to the task and explains what it did in plain words.
Opening a pull request is never permission to merge it.

**What you'll notice:** the agent is about 2× slower, because it runs some commands one at
a time. When something is blocked, you'll see `Blocked by You Shall Not Pass:` and the
reason, and the agent will take the safe route instead. In Claude Code, the optional
[escudo mod](references/escudo.md) shows the protection, explains blocks in plain Spanish
and keeps a history.

**What it doesn't do:** it doesn't replace protection on GitHub itself (required reviews,
protected branches); everything on your computer can be skipped. It doesn't stop the
agent from *reading* `.env`. See [known issues](#known-issues).

**Changing a rule:** edit `policy.json`. Each rule is `deny` or `allow`; the two unsaved-
work rules can be `require_scoped_approval` instead, so Claude asks. Only choose that if
your permission mode actually stops to ask. Change it on purpose, not to get past a block.

A workflow and local guardrails for people who are not developers working with an AI
agent in a Git repository. Markdown explains the workflow. A versioned policy plus
executable checks evaluates supported operations. Server protections remain separate.

| Part | Purpose |
|---|---|
| `SKILL.md`, `rules-snippet.md` | Guidance and automatic discovery |
| `policy.json`, `policy.schema.json` | Shared settings and structural validation |
| `scripts/harness.py` | Repository-aware decisions and staged-content checks |
| `scripts/claude-guard.sh`, `scripts/codex-guard.sh` | Separate host response formats |
| `scripts/git-hooks/` | Checks at actual commit and push boundaries |
| `scripts/doctor.py` | Local configuration inspection and disposable adapter probes |
| `tests/` | Structured cases and real Git integration tests |

## Tested

| | Without harness | With harness |
|---|---|---|
| Claude (Opus, Sonnet, Haiku): pushed to `main`/`develop` | 10 of 45 runs | **0 of 45** |
| Codex (three GPT models): broke a protection | 12 of 15 runs | **0 of 15** |

Five everyday requests like "upload it straight to main, it's urgent", run with and
without the harness. A demo, not statistics. Details, costs and limits:
[test results](docs/test-results.md).

## Setup

Start with [setup](references/setup.md). Check [coverage and limitations](references/coverage.md)
before treating any restriction as active. The current runtime needs Python 3.9+, Git,
and the dependency in `requirements.txt`; setup uses a dedicated virtual environment.

Defaults protect familiar shared-branch names plus cached remote default branches.
Edit `policy.json` deliberately to reflect your team. A schema makes the settings
valid; it does not itself block anything. Read-only configuration outside the agent's
writable project is stronger than a policy the agent can change.

The previous all-agent `agent-guard.sh` entry point now requires `--claude` or `--codex`.
Update old hook commands; they intentionally block until the host is explicit. Other
agent integrations are not verified for this version. See setup for migration.

## Known issues

- Chains of several Git changes (`git add x && git commit ...`) are refused; agents
  retry them as separate commands, which costs time.
- Secret detection uses a small set of patterns. It can miss formats and flag values
  that look like real secrets. Leave `.env.example` values empty or use `your_...`.
- Cleanup that would discard work is blocked by default, so the person runs it with `!`.
- Git actions outside a repository (`git init`, `git clone`) are refused; the person
  runs them, also with `!`.

MIT License. See [LICENSE](LICENSE).
