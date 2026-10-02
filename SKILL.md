---
name: you-shall-not-pass
description: "Guide safe repository work for non-technical users: prepare a working branch, save and share through a pull request, preserve unsaved work, and respond to leaked credentials. Use before repository edits or Git mutations and when setting up these guardrails. General explanations outside a repository do not require this workflow."
---

# You Shall Not Pass

Help the person complete their work without losing it or changing a shared branch by
accident. Explain significant changes in one short, plain sentence. Group routine
inspection into one explanation; do not turn every Git command into another question.

## Guidance, policy, and actual checks

This file guides behavior. `rules-snippet.md` makes the workflow discoverable from the
agent's always-read instructions. Neither file is an enforcement boundary.

`policy.json` is the single source of configurable decisions. `policy.schema.json`
checks its structure; `scripts/harness.py` evaluates supported operations using actual
repository state. The policy has no executable effect unless its checks are installed
and invoked. See [coverage](references/coverage.md) for supported paths and gaps.

Read `policy.json` before Git mutations. Do not silently change the policy to make a
blocked task succeed. Prefer a working branch and a pull request. If the person wants
a policy change, treat it as a separate, explicit configuration change, with its effects
made clear. Local checks remain bypassable; server restrictions are a separate layer.

## Start work without disturbing existing changes

1. Inspect the current branch, staged files, and unsaved work. Identify which changes
   belong to this task; do not stage, erase, stash, or overwrite unrelated work.
2. Identify the repository's default branch and any explicitly designated team base.
   Use cached `refs/remotes/<remote>/HEAD` or the hosting service. Do not guess that the
   base is `main`. If the hook reports an unknown default, follow the setup instructions
   rather than trying a different command spelling.
3. For a clean new task, fetch and create a working branch from the agreed base's remote
   reference. There is no need to switch to and update the local base first. Keep an
   existing working branch for related changes. With unsaved work, a new branch can
   preserve it; pause only if the next operation would lose or misattribute work.
4. Use a separate worktree for concurrent work. Explain that ignored environment files
   and installed packages are not automatically copied.

Run each state-changing Git command on its own; read-only commands may be grouped with
it. The guard does not simulate chains of changes such as `git switch -c work && git
commit ...`, so each change is checked against the state at execution time.

## Save the intended changes

- Work on a personal branch. By default, commits and edits on a shared branch are blocked.
- Review the diff, stage the intended files by name, and inspect the staged content.
  Avoid sweeping unrelated files into a commit. Do not assume a filename ending in
  `.example` makes its contents safe.
- Keep credentials out of every committed file, not only `.env`. Share configuration
  through an empty or placeholder example and ignore the private environment file.
  Content detection is limited; passing a scan is not proof that no credential exists.
- Commit the inspected index with a short message explaining the change. Do not skip
  checks. If a check blocks a command, explain the reason and use the documented safe
  workflow; never route the same action through another interpreter or tool.

## Share only within the person's authorization

“Upload it,” “push it,” “send it to the team,” and “open a PR” authorize sharing the
current task. Use that permission without asking again for each step. Push the working
branch to an explicit remote and open a PR against the agreed base. Do not upload
unrelated work or treat that permission as covering later, separate tasks.

The default policy denies direct pushes to protected branches, force pushes, and
remote-branch deletion. Shared-branch merges include local fast-forward merges. Use
a reviewed PR workflow. A PR's creation does not authorize merging it on the server.
Keep the description focused on what changed and what a reviewer should check.

If needed, fetch and merge the base into the working branch. Avoid rewriting published
history. If only a local remote exists or hosting access is unavailable, state exactly
what was shared and what remains incomplete; do not claim a PR was opened.

## Approval for loss of work

A request such as “start over,” “clean this up,” or “undo my attempt” authorizes
inspection, not deleting unrelated or unidentified work. Before destructive cleanup:

1. Identify the exact affected files or branches and what will disappear.
2. Preserve a recoverable backup when appropriate; keep private files private.
3. Reuse existing explicit approval only when it covers that operation and that work.
   Otherwise explain the concrete loss and ask once, then wait. A backup is not approval.
4. Do not expand the scope after approval. If the affected work changes, review it again.

This applies to reset/restore/clean, deletion through shell or file tools, forced branch
changes, deleting saved stashes, and history rewriting. Normal editing and already-
authorized uploads do not require repeated confirmation.

Claude's adapter requests host approval for supported destructive commands. Codex's
adapter blocks them because its current PreToolUse protocol cannot request approval.
A chat “yes” does not unlock that block. Follow the human-controlled path in
[setup](references/setup.md); do not fabricate approval records, turn off the hook,
or use another tool to get around it.

## Recovery and setup

For a leaked credential, use [the leaked-key procedure](references/leaked-key.md).
Do not print the credential or claim deleting a file removes copies from history.

For conflicts or uncertain errors, preserve the state, explain what is known, and
ask for the missing decision or help from a developer when needed. Harmless warnings
are not automatically a reason to abandon authorized work.

For installation or changes to protection settings, follow [setup](references/setup.md).
Show the intended scope. Reuse explicit authorization already given for that scope;
do not request it again. Run the diagnostic and live smoke tests. Report “configured,”
“tested,” and “unverified” accurately; never call the computer protected merely because
configuration files exist.
