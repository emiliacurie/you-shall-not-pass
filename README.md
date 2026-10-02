# oops-proof

A personal harness for AI coding agents. The skill inside is named `personal-harness`.

**What it does for you:** when you ask an AI coding agent to "fix the footer" or "upload
it", the agent works on its own branch and opens a pull request instead of changing the
team's shared branch. It also keeps secrets like `.env` out of commits and stops before
deleting unsaved work. It's tested on Claude Code and Codex. A developer installs it
once; after that it works in the background.

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
- Codex can't ask for approval, so cleanup that would discard work is blocked there.

MIT License. See [LICENSE](LICENSE).
