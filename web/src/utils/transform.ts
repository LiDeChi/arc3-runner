import type { TransformSpec } from '../types'

function asNumber(value: unknown, fallback = 0): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback
}

function opName(spec: TransformSpec | null | undefined): string {
  return String(spec?.op ?? '').toLowerCase().replaceAll('-', '_')
}

function mappingEntries(value: unknown): string {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return ''
  return Object.entries(value as Record<string, unknown>)
    .map(([source, target]) => `${source}->${String(target)}`)
    .join(',')
}

export function readableTransform(spec: TransformSpec | null | undefined): string {
  const op = opName(spec)
  if (!spec || !op) return 'unknown'

  if (op === 'identity' || op === 'i') return 'I'
  if (op === 'translate' || op === 't') return `T(${asNumber(spec.dx)},${asNumber(spec.dy)})`
  if (op === 'rotate' || op === 'r') {
    const degrees = ((asNumber(spec.k) % 4) + 4) % 4 * 90
    const pivot = typeof spec.pivot === 'string' && spec.pivot !== 'grid' ? `@${spec.pivot}` : ''
    return `R${degrees}${pivot}`
  }
  if (op === 'mirror' || op === 'm') return `M(${String(spec.axis ?? '?')})`
  if (op === 'scale' || op === 's') return `S(${asNumber(spec.factor ?? spec.f, 1)})`
  if (op === 'color_map' || op === 'colormap' || op === 'c') {
    const entries = mappingEntries(spec.mapping)
    return entries ? `C{${entries}}` : 'C'
  }
  if (op === 'toggle' || op === 'g') {
    const count = Array.isArray(spec.cells) ? spec.cells.length : 0
    return `G{${count} cells}`
  }
  if (op === 'compose') {
    const children = Array.isArray(spec.fs) ? spec.fs : []
    return children.map((child) => readableTransform(child as TransformSpec)).join(' ∘ ') || 'compose'
  }
  if (op === 'periodic') {
    return `[${readableTransform(spec.f as TransformSpec)}]×${asNumber(spec.n)} → ${readableTransform(spec.g as TransformSpec)}`
  }
  if (op === 'conditional') {
    return `if ${predicateLabel(spec.pred)}: ${readableTransform((spec.if_true ?? spec.f) as TransformSpec)}`
  }
  return op
}

export function shortTransformLabel(spec: TransformSpec | null | undefined): string {
  const op = opName(spec)
  if (op === 'toggle') return 'G'
  if (op === 'color_map' || op === 'colormap') return 'C'
  if (op === 'conditional') return 'if'
  if (op === 'identity') return 'I'
  if (!op) return '?'
  return readableTransform(spec)
}

function predicateLabel(value: unknown): string {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return '?'
  const pred = value as Record<string, unknown>
  if (pred.region && typeof pred.region === 'object') return 'region'
  return `${String(pred.axis ?? 'x')}${String(pred.op ?? '>')}${String(pred.value ?? '?')}`
}
