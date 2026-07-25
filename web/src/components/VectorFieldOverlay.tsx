import type { TransformSpec } from '../types'
import { readableTransform, shortTransformLabel } from '../utils/transform'

interface VectorFieldOverlayProps {
  spec: TransformSpec | null | undefined
  label?: string
  compact?: boolean
}

function opName(spec: TransformSpec | null | undefined): string {
  return String(spec?.op ?? '').toLowerCase().replaceAll('-', '_')
}

function asNumber(value: unknown, fallback = 0): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback
}

function children(value: unknown): TransformSpec[] {
  return Array.isArray(value) ? value.filter((item): item is TransformSpec => !!item && typeof item === 'object' && 'op' in item) : []
}

export function VectorFieldOverlay({ spec, label, compact = false }: VectorFieldOverlayProps) {
  const op = opName(spec)
  const readable = label ?? readableTransform(spec)

  if (!spec) {
    return <span className="vector-badge empty">?</span>
  }

  if (op === 'translate' || op === 't') {
    const dx = asNumber(spec.dx)
    const dy = asNumber(spec.dy)
    const x2 = 18 + Math.max(-11, Math.min(11, dx * 9))
    const y2 = 18 + Math.max(-11, Math.min(11, dy * 9))
    return (
      <span className={`vector-glyph ${compact ? 'compact' : ''}`} title={readable}>
        <svg viewBox="0 0 36 36" aria-hidden="true">
          <defs>
            <marker id={`arrow-${dx}-${dy}`} markerWidth="5" markerHeight="5" refX="4" refY="2.5" orient="auto">
              <path d="M0,0 L5,2.5 L0,5 Z" />
            </marker>
          </defs>
          <circle cx="18" cy="18" r="2.5" />
          <path d={`M18 18 L${x2} ${y2}`} markerEnd={`url(#arrow-${dx}-${dy})`} />
        </svg>
        {!compact && <code>{readable}</code>}
      </span>
    )
  }

  if (op === 'rotate' || op === 'r') {
    const k = ((asNumber(spec.k) % 4) + 4) % 4
    const sweep = k === 3 ? 0 : 1
    return (
      <span className={`vector-glyph ${compact ? 'compact' : ''}`} title={readable}>
        <svg viewBox="0 0 36 36" aria-hidden="true">
          <defs>
            <marker id={`arc-${k}`} markerWidth="5" markerHeight="5" refX="4" refY="2.5" orient="auto">
              <path d="M0,0 L5,2.5 L0,5 Z" />
            </marker>
          </defs>
          <path d={`M25 11 A10 10 0 1 ${sweep} 11 25`} markerEnd={`url(#arc-${k})`} />
          <text x="18" y="20">{90 * k}</text>
        </svg>
        {!compact && <code>{readable}</code>}
      </span>
    )
  }

  if (op === 'mirror' || op === 'm') {
    const axis = String(spec.axis ?? 'x')
    const axisPath = axis === 'y' ? 'M18 5 L18 31' : axis === 'diag' ? 'M7 29 L29 7' : 'M5 18 L31 18'
    return (
      <span className={`vector-glyph ${compact ? 'compact' : ''}`} title={readable}>
        <svg viewBox="0 0 36 36" aria-hidden="true">
          <path className="axis" d={axisPath} />
          <path d="M10 13 L15 13 M21 13 L26 13" />
          <path d="M10 23 L15 23 M21 23 L26 23" />
        </svg>
        {!compact && <code>{readable}</code>}
      </span>
    )
  }

  if (op === 'compose') {
    return (
      <span className={`vector-compose ${compact ? 'compact' : ''}`} title={readable}>
        {children(spec.fs).map((child, index) => (
          <span className="vector-compose-item" key={index}>
            {index > 0 && <span className="compose-mark">∘</span>}
            <VectorFieldOverlay spec={child} compact />
          </span>
        ))}
      </span>
    )
  }

  if (op === 'periodic') {
    return (
      <span className={`vector-periodic ${compact ? 'compact' : ''}`} title={readable}>
        <VectorFieldOverlay spec={spec.f as TransformSpec} compact />
        <span className="periodic-count">×{asNumber(spec.n)}</span>
        <span className="compose-mark">→</span>
        <VectorFieldOverlay spec={spec.g as TransformSpec} compact />
      </span>
    )
  }

  return (
    <span className={`vector-badge ${compact ? 'compact' : ''}`} title={readable}>
      {shortTransformLabel(spec)}
    </span>
  )
}
