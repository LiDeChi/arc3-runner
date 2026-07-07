import type { TransformSpec } from '../types'

interface VectorFieldOverlayProps {
  transform?: TransformSpec
}

export function VectorFieldOverlay({ transform }: VectorFieldOverlayProps) {
  if (!transform || transform.op !== 'translate') {
    return <span className="vector-field-empty">no vector</span>
  }

  const dx = Number(transform.dx ?? 0)
  const dy = Number(transform.dy ?? 0)
  const scale = 12
  const x1 = 24
  const y1 = 24
  const x2 = x1 + dx * scale
  const y2 = y1 + dy * scale

  return (
    <svg className="vector-field-overlay" viewBox="0 0 48 48" aria-label={`T(${dx},${dy}) vector`}>
      <defs>
        <marker id="vector-arrow" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">
          <path d="M0,0 L6,3 L0,6 Z" />
        </marker>
      </defs>
      <line x1={x1} y1={y1} x2={x2} y2={y2} markerEnd="url(#vector-arrow)" />
      <circle cx={x1} cy={y1} r="2" />
    </svg>
  )
}
