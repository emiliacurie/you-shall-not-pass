# Escudo: see the guard working (Claude Code mod)

The guard blocks silently from the person's point of view: a technical line in the
transcript and nothing else. The escudo mod makes it visible. It is optional and only
observes the guard's decisions; removing it changes no protection.

| What | How it looks |
|---|---|
| Protection status | A line above the prompt: green `🛡 ux-fix · tu rama de trabajo`, red `🛡 main · rama compartida, protegida`, yellow `⚠ El guardián no está instalado` |
| Plain explanations | A toast per block, in Spanish: `🛡 Bloqueado: Intentó subir directo a una rama compartida…` |
| History | `/escudo` opens a pane with the last 100 blocks across sessions: time, project, explanation, exact command |

## Install

Requires Claude Code 2.1.287 or later and the guard installed at `~/.you-shall-not-pass`.

1. Copy `mods/escudo` to a folder outside any project, for example `~/.claude/mods/escudo`.
2. Add that folder to `CLAUDE_CODE_PLUGIN_DIRS` in the `env` block of
   `~/.claude/settings.json` (separate several folders with `:`).
3. Start a new session. Check it with `claude plugin test ~/.claude/mods/escudo`.

## How it works

- Status reads the installed `policy.json`, the current branch and the remotes' default
  branches, after every shell command and every turn.
- A block is recognized by the text `You Shall Not Pass` in a failed tool call. Each
  guard message maps to a Spanish explanation; an unknown one reads "El guardián
  bloqueó esta acción."
- History is stored in the mod's own storage, not in the repository.

## Limits

- Claude Code only. Codex has no equivalent.
- If the guard's messages change, update the explanations in `mods/escudo/hooks/escudo.ts`
  and their tests.
- The status line shows the session's folder. Commands that target another repository
  with `git -C` are guarded but not reflected in the line.
