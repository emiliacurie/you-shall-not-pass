export type Status =
  | { kind: 'missing' }
  | { kind: 'outside' }
  | { kind: 'protected' | 'working'; branch: string }

export type Block = { at: number; project: string; action: string; reason: string }

const MAX_HISTORY = 100

const EXPLANATIONS: [RegExp, string][] = [
  [/Push a working branch|actual destination is a protected/i, 'Intentó subir directo a una rama compartida. Lo correcto es subir tu rama y abrir un PR.'],
  [/discard work|overwrite existing work|alter in-progress work|Deletion requires approval/i, 'Esto habría borrado trabajo sin guardar. Si de verdad quieres borrarlo, hazlo tú con !.'],
  [/changes history|Amending rewrites/i, 'Esto habría reescrito el historial. Si de verdad quieres hacerlo, hazlo tú con !.'],
  [/before committing/i, 'Intentó guardar un commit en una rama compartida. Primero hay que crear una rama de trabajo.'],
  [/before editing shared-branch/i, 'Intentó editar archivos en una rama compartida. Primero hay que crear una rama de trabajo.'],
  [/Force push|preserve remote history/i, 'Intentó un push forzado, que puede reemplazar el historial del equipo.'],
  [/Remote branch deletion|Deleting a remote ref/i, 'Intentó borrar una rama en GitHub.'],
  [/environment file|Environment files/i, 'Intentó guardar un archivo .env con datos privados.'],
  [/resembles a credential/i, 'Lo que iba a guardar parece una contraseña o una llave, así que no se guardó.'],
  [/Skipping checks/i, 'Intentó saltarse las revisiones de seguridad.'],
  [/reviewed pull request, including fast-forward/i, 'Intentó mezclar cambios directo en una rama compartida. Eso va por un PR.'],
  [/Shell substitutions|Wrapper commands|Environment-prefixed|Cannot parse/i, 'El comando era demasiado complejo para revisarlo. Claude debe correrlo de forma más simple.'],
  [/separately|own command/i, 'Juntó varios comandos de git en uno. Deben ir uno por uno.'],
  [/inside a repository/i, 'Acción de git fuera de un repositorio, como crear o clonar uno. Hazla tú con !.'],
  [/validation or inspection failed|Default branch is unknown|Could not inspect/i, 'El guardián no pudo revisar el estado y bloqueó por precaución.'],
]

export function isGuardBlock(text: string | undefined) {
  return Boolean(text && /You Shall Not Pass/i.test(text))
}

export function explain(reason: string) {
  return EXPLANATIONS.find(([pattern]) => pattern.test(reason))?.[1] ?? 'El guardián bloqueó esta acción.'
}

export function protection(
  branch: string | undefined,
  protectedNames: readonly string[],
  defaults: readonly string[],
): Status {
  if (branch === undefined) return { kind: 'outside' }
  const isShared = branch === 'HEAD' || protectedNames.includes(branch) || defaults.includes(branch)
  return { kind: isShared ? 'protected' : 'working', branch: branch === 'HEAD' ? 'sin rama' : branch }
}

export function actionOf(tool: string, input: { command?: unknown; file_path?: unknown }) {
  if (typeof input.command === 'string') return input.command.replace(/\s+/g, ' ').trim().slice(0, 70)
  if (typeof input.file_path === 'string') return `${tool} ${input.file_path.split('/').at(-1)}`
  return tool
}

export function remember(history: readonly Block[], block: Block) {
  return [block, ...history].slice(0, MAX_HISTORY)
}

export function sameDay(a: number, b: number) {
  return new Date(a).toDateString() === new Date(b).toDateString()
}

export function blocksToday(history: readonly Block[], now: number) {
  return history.filter(block => sameDay(block.at, now)).length
}

export function clock(at: number) {
  const date = new Date(at)
  return `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
}

export function statusLine(status: Status, today: number) {
  const count = today > 0 ? ` · ${today} ${today === 1 ? 'bloqueo' : 'bloqueos'} hoy` : ''
  switch (status.kind) {
    case 'missing':
      return { text: '⚠ El guardián no está instalado', level: 'warning' as const }
    case 'outside':
      return { text: `🛡 Guardián activo · fuera de un repositorio${count}`, level: 'subtle' as const }
    case 'protected':
      return { text: `🛡 ${status.branch} · rama compartida, protegida${count}`, level: 'error' as const }
    case 'working':
      return { text: `🛡 ${status.branch} · tu rama de trabajo${count}`, level: 'success' as const }
  }
}
