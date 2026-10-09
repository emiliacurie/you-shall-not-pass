import type { EngineInterface, Register } from 'claude-code'

import {
  type Block,
  type Status,
  actionOf,
  blocksToday,
  clock,
  explain,
  isGuardBlock,
  protection,
  remember,
  statusLine,
} from './escudo'

const PANE = 'escudo'
const HISTORY_KEY = 'historial'

let status: Status = { kind: 'outside' }
let history: Block[] = []
let now = 0

async function git($: EngineInterface, args: string[]) {
  const ran = await $.process.run(['git', ...args], { cwd: await $.session.cwd() })
  return ran.exitCode === 0 ? ran.stdout.trim() : undefined
}

async function protectedNames($: EngineInterface) {
  const home = await $.env.get('HOME')
  const path = `${home}/.you-shall-not-pass/policy.json`
  if (!(await $.fs.exists(path))) return undefined
  const policy = JSON.parse(String(await $.fs.read(path))) as { protected_branches?: { additional?: string[] } }
  return policy.protected_branches?.additional ?? []
}

async function readStatus($: EngineInterface) {
  const names = await protectedNames($)
  if (!names) return { kind: 'missing' } as const
  if ((await git($, ['rev-parse', '--is-inside-work-tree'])) !== 'true') return { kind: 'outside' } as const
  const branch = await git($, ['rev-parse', '--abbrev-ref', 'HEAD'])
  const heads = (await git($, ['for-each-ref', '--format=%(symref:lstrip=3)', 'refs/remotes/*/HEAD'])) ?? ''
  return protection(branch, names, heads.split('\n').filter(Boolean))
}

async function refresh($: EngineInterface) {
  status = await readStatus($)
  now = await $.clock.now()
  $.ui.invalidate('ui.render')
}

async function project($: EngineInterface) {
  return (await $.session.cwd()).split('/').filter(Boolean).at(-1) ?? ''
}

async function record($: EngineInterface, action: string, reason: string) {
  const plain = explain(reason)
  history = remember(history, { at: await $.clock.now(), project: await project($), action, reason: plain })
  await $.store.set(HISTORY_KEY, history)
  $.ui.toast(`🛡 Bloqueado: ${plain}`)
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    const saved = await $.store.get(HISTORY_KEY).catch(() => undefined)
    history = Array.isArray(saved) ? (saved as Block[]) : []
    await refresh($).catch(() => {})
    await $.command
      .register({ name: 'escudo', description: 'Abre el historial de lo que bloqueó You Shall Not Pass' })
      .catch(() => {})
    return next(e)
  })

  on('tool.call', async ($, e, next) => {
    const ran = await next(e)
    const reason = ran.deny ?? (ran.isError ? ran.text : undefined)
    if (isGuardBlock(reason)) {
      await record($, actionOf(e.tool, e as { command?: unknown; file_path?: unknown }), reason ?? '').catch(() => {})
    }
    if (e.tool === 'Bash') await refresh($).catch(() => {})
    return ran
  })

  on('turn.complete', async ($, e, next) => {
    const result = await next(e)
    await refresh($).catch(() => {})
    return result
  })

  on('command.run', { command: 'escudo' }, async $ => {
    await refresh($).catch(() => {})
    await $.ui.open({ id: PANE, title: 'Escudo' })
    return { text: 'Historial del escudo abierto.' }
  }).catch(() => ({ text: 'No pude abrir el escudo.' }))

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    if (e.props.hasSurvey) return next(e)
    const { Box, Text } = $.ui.resolve(e)
    const line = statusLine(status, blocksToday(history, now))
    const ours = (
      <Text color={line.level} bold={line.level !== 'subtle'}>
        {` ${line.text} `}
      </Text>
    )
    const above = await next(e).catch(() => null)
    if (!above) return ours

    return (
      <Box flexDirection="column">
        {above}
        {ours}
      </Box>
    )
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Box, Text } = $.ui.resolve(e)
    const line = statusLine(status, blocksToday(history, now))

    return (
      <Box flexDirection="column">
        <Text color={line.level} bold>
          {line.text}
        </Text>
        <Text> </Text>
        {history.length === 0 && <Text color="subtle">Todavía no ha bloqueado nada.</Text>}
        {history.slice(0, 30).map(block => (
          <Box flexDirection="column">
            <Text>
              <Text color="subtle">{clock(block.at)} · {block.project}</Text>
            </Text>
            <Text bold>{block.reason}</Text>
            <Text color="subtle">{block.action}</Text>
            <Text> </Text>
          </Box>
        ))}
      </Box>
    )
  })
}
