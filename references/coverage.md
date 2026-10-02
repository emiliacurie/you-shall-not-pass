# What these checks cover

This version is a local guardrail, not a complete shell sandbox. Do not call it
unbreakable or label every tool supported because its configuration resembles another.

| Layer | Supported check | Important limit |
|---|---|---|
| Policy schema | Required fields, choices, unknown fields, branch-name validation | Structure is not proof an operation is safe |
| Git pre-commit | Current shared/detached branch, staged `.env` names, selected credential patterns in staged blobs | `--no-verify`, alternate hooks paths, other ways to create commits, and other credential formats can bypass or evade it |
| Git pre-push | Actual destination refs, deletion, ancestry of proposed update | Local hooks can be skipped; no comprehensive scan of previously committed history |
| Agent shell check | Simple Git commands, `git -C`, explicit pushes, shared-branch merges, supported cleanup/history commands, skip-check flags | Does not evaluate arbitrary programs, Git aliases, every option abbreviation, or general shell semantics |
| Agent edit check | Known file-edit tools and patch target paths on shared/detached branches | Shell/Python file writes and other tool paths are not a complete protected-file boundary |
| Claude adapter | No permission override for safe calls, deny for blocks, ask for scoped approval | Host permission mode/UI determines what happens to ask; test that it actually stops unattended work |
| Codex adapter | No override for safe calls, deny for blocks and approval-required operations | No native ask response is emitted; a chat approval does not unlock a deny |
| Doctor | Valid policy, effective Git hooksPath, executable hooks, isolated adapter probes | Cannot prove the running agent loaded hooks, or verify server restrictions |

Unsupported state-changing Git commands are refused. A chain may hold one Git change
plus read-only commands (Git inspection, `cat`, `grep`, `head` and similar); chains of
several changes are refused. Quoted multi-line commit messages and heredoc messages with
a quoted delimiter are read as literal text.
Never respond to a block by disguising the operation in Python or another interpreter.
Such arbitrary code execution remains a known limitation, not a sanctioned workaround.

Cached remote default branches join the configured protected names. Missing remote HEAD
information blocks mutations until setup resolves it. This cache can become stale;
refresh it after the team changes the default. Without a remote, only configured names
are known. A team base different from the default must be listed explicitly.

A Git hook examines repository state at its actual boundary. The agent hook observes
state before a tool call; another process can still change it afterward. Separate
worktrees reduce interference but do not make local checks tamper-proof. Fast-forward
merges do not invoke pre-commit; the supported agent check and server rules are separate
protections for those operations.

Credential detection uses a small set of private-key/token patterns and credential
assignments. It can produce false positives and miss secrets. Values that start with `your_`
or `my_`, or consist only of `x`, `*` or `.`, count as placeholders. Placeholders and
example filenames are not substitutes for a proper secret scanner. Do not log matched values.
The checks do not prevent reading `.env`; use the host's filesystem permissions for
that goal, considering all reading tools rather than a single Read-tool rule.

If policy loading or inspection fails, the executable exits with code 2 rather than
silently accepting the action. Missing executables, host timeouts, disabled hooks and
host-level failures can behave differently: verify them in the real host. Do not infer
fail-closed behavior for every failure just from the script's error handler.

The included installer preserves ordinary `.git/hooks/pre-commit` and `pre-push` by
chaining them and stops if a different hooksPath already exists. Repositories with
custom hook managers require explicit integration. A linked worktree uses the common
Git directory for chaining. Existing hooks can still have their own behavior and risks.

## Verification status

Read `tests/VALIDATION.md` for the current run results. Local protocol tests, actual Git
hook tests, and live host tests are different kinds of evidence. Older Claude reports
and the earlier guidance-only Codex experiment do not certify this new implementation.

Official references checked for the integration design:
- [Codex hooks](https://learn.chatgpt.com/docs/hooks): supported blocking responses,
  unsupported ask response, tool coverage, host failure behavior.
- [Claude hooks](https://code.claude.com/docs/en/hooks): PreToolUse allow/deny/ask protocol.
- [Git hooks](https://git-scm.com/docs/githooks): actual commit/push boundaries and bypasses.
