import { test, expect } from 'claude-code/testing'

import { actionOf, blocksToday, explain, isGuardBlock, protection, remember, statusLine } from './escudo'

test('recognizes the guard by its name', () => {
  expect(isGuardBlock('PreToolUse:Bash hook error: You Shall Not Pass: Push a working branch')).toBe(true)
  expect(isGuardBlock('command not found')).toBe(false)
  expect(isGuardBlock(undefined)).toBe(false)
})

test('explains the real guard messages in plain Spanish', () => {
  expect(explain('You Shall Not Pass: Push a working branch and open a pull request instead of updating a shared branch.')).toContain('abrir un PR')
  expect(explain('You Shall Not Pass: This can discard work. Approval must cover the affected files')).toContain('borrado trabajo sin guardar')
  expect(explain('You Shall Not Pass: Shell substitutions cannot be checked as a single operation.')).toContain('demasiado complejo')
  expect(explain('You Shall Not Pass: Run this Git action inside a repository.')).toContain('fuera de un repositorio')
  expect(explain('Blocked by You Shall Not Pass: validation or inspection failed.')).toContain('por precaución')
  expect(explain('You Shall Not Pass: something new')).toBe('El guardián bloqueó esta acción.')
})

test('working branches are safe; configured and default branches are protected', () => {
  expect(protection('ux-fix', ['main'], ['develop'])).toEqual({ kind: 'working', branch: 'ux-fix' })
  expect(protection('main', ['main'], [])).toEqual({ kind: 'protected', branch: 'main' })
  expect(protection('release/v0.1', ['main'], ['release/v0.1'])).toEqual({ kind: 'protected', branch: 'release/v0.1' })
  expect(protection('HEAD', ['main'], [])).toEqual({ kind: 'protected', branch: 'sin rama' })
  expect(protection(undefined, ['main'], [])).toEqual({ kind: 'outside' })
})

test('the status line reads green, red or yellow with today\'s blocks', () => {
  expect(statusLine({ kind: 'working', branch: 'ux-fix' }, 0)).toEqual({ text: '🛡 ux-fix · tu rama de trabajo', level: 'success' })
  expect(statusLine({ kind: 'protected', branch: 'main' }, 2).text).toBe('🛡 main · rama compartida, protegida · 2 bloqueos hoy')
  expect(statusLine({ kind: 'missing' }, 0).level).toBe('warning')
})

test('history keeps the newest first and counts only today', () => {
  const now = Date.parse('2026-10-09T15:00:00Z')
  const yesterday = { at: now - 86400000 * 2, project: 'a', action: 'x', reason: 'r' }
  const today = { at: now - 60000, project: 'b', action: 'y', reason: 'r' }
  const history = remember(remember([], yesterday), today)
  expect(history[0]).toBe(today)
  expect(blocksToday(history, now)).toBe(1)
})

test('actions read as the command or the edited file', () => {
  expect(actionOf('Bash', { command: 'git   push origin HEAD:main' })).toBe('git push origin HEAD:main')
  expect(actionOf('Edit', { file_path: '/repo/app/models/user.rb' })).toBe('Edit user.rb')
})
