import type { On } from 'claude-code'
import { test, expect, mock } from 'claude-code/testing'

const POLICY = JSON.stringify({ protected_branches: { additional: ['main', 'develop'] } })

function stubEngine(on: On, { branch = 'main', hasGuard = true } = {}) {
  const store = new Map<string, unknown>()
  const toasts: string[] = []
  mock.clock(on, { now: Date.parse('2026-10-09T15:00:00Z') })
  on('session.start', ($, e) => ({ cwd: e.cwd }))
  on('session.cwd', () => ({ value: '/Users/arely/simpledocs' }))
  on('command.register', ($, e) => ({ value: { command: e.name } }))
  on('env.get', () => ({ value: '/Users/arely' }) as never)
  on('fs.exists', () => ({ value: hasGuard }) as never)
  on('fs.read', () => ({ value: POLICY }) as never)
  on('process.run', ($, e) => {
    const args = (e as { argv: string[] }).argv.join(' ')
    const stdout = args.includes('--is-inside-work-tree') ? 'true\n' : args.includes('--abbrev-ref') ? `${branch}\n` : 'develop\n'
    return { value: { exitCode: 0, stdout, stderr: '' } } as never
  })
  on('store.get', ($, e) => ({ value: store.get(e.key) }))
  on('store.set', ($, e) => {
    store.set(e.key, e.value)
    return { value: undefined }
  })
  on('ui.toast', ($, e) => {
    toasts.push(String((e as { text?: string }).text ?? e))
    return { value: undefined } as never
  })
  return { store, toasts }
}

const start = { cwd: '/Users/arely/simpledocs', surface: 'terminal', isInteractive: true } as const
const bandProps = { hasSurvey: false, isWorking: false, maxRows: 10, bodyColumns: 80 } as never

async function lineOf($: Parameters<Parameters<typeof test>[1]>[0]) {
  const ui = await $.ui.mount({ plugin: 'escudo', surface: 'terminal', component: 'AbovePrompt', props: bandProps })
  return (await ui.findAll({ type: 'Text' })).map(t => t.text ?? '').join('|')
}

test('on a shared branch the line warns it is protected', async ($, on) => {
  stubEngine(on, { branch: 'main' })
  await $.session.start(start)
  expect(await lineOf($)).toContain('main · rama compartida, protegida')
})

test('on a working branch the line says it is yours', async ($, on) => {
  stubEngine(on, { branch: 'ux-fix' })
  await $.session.start(start)
  expect(await lineOf($)).toContain('ux-fix · tu rama de trabajo')
})

test('without the guard installed the line says so', async ($, on) => {
  stubEngine(on, { hasGuard: false })
  await $.session.start(start)
  expect(await lineOf($)).toContain('no está instalado')
})

test('a guard block shows a plain explanation and lands in the history', async ($, on) => {
  const { store, toasts } = stubEngine(on, { branch: 'ux-fix' })
  on('tool.call', () => ({
    result: undefined,
    isError: true,
    text: 'PreToolUse:Bash hook error: You Shall Not Pass: Push a working branch and open a pull request instead of updating a shared branch.',
  }) as never)
  await $.session.start(start)
  await $.tool.call({ tool: 'Bash', command: 'git push origin HEAD:main' } as never).catch(() => undefined)
  expect(toasts.join(' ')).toContain('abrir un PR')
  const saved = store.get('historial') as { action: string; project: string }[]
  expect(saved[0]).toEqual(expect.objectContaining({ action: 'git push origin HEAD:main', project: 'simpledocs' }))
  expect(await lineOf($)).toContain('1 bloqueo hoy')
})

test('other tool errors are ignored', async ($, on) => {
  const { toasts } = stubEngine(on, { branch: 'ux-fix' })
  on('tool.call', () => ({ result: undefined, isError: true, text: 'command not found' }) as never)
  await $.session.start(start)
  await $.tool.call({ tool: 'Bash', command: 'foo' } as never).catch(() => undefined)
  expect(toasts).toEqual([])
})

test('the history pane lists the block on terminal and desktop', async ($, on) => {
  stubEngine(on, { branch: 'ux-fix' })
  on('tool.call', () => ({ result: undefined, isError: true, text: 'You Shall Not Pass: This can discard work.' }) as never)
  await $.session.start(start)
  await $.tool.call({ tool: 'Bash', command: 'git restore -- notas.txt' } as never).catch(() => undefined)
  for (const surface of ['terminal', 'desktop'] as const) {
    const ui = await $.ui.mount({ plugin: 'escudo', surface, component: 'Pane', requestId: 'escudo', props: { title: 'Escudo' } as never })
    const text = (await ui.findAll({ type: 'Text' })).map(t => t.text ?? '').join('|')
    expect(text).toContain('borrado trabajo sin guardar')
    expect(text).toContain('git restore -- notas.txt')
  }
})
