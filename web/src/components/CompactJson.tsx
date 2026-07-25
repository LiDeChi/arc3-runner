import { type ReactNode } from 'react'

interface CompactJsonProps {
  value: unknown
  /** Default expand depth for nested objects/arrays (negative = collapse all) */
  defaultExpand?: number
  /** Label shown before the value */
  label?: string
  /** Max items shown before "show all" toggle */
  maxPreview?: number
}

function isPrimitive(value: unknown): boolean {
  return value === null || value === undefined || typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean'
}

function isFlatArray(value: unknown[]): boolean {
  return value.every((v) => isPrimitive(v))
}

function isNumberMatrix(value: unknown[]): boolean {
  return value.every((v) => Array.isArray(v) && v.every((c) => typeof c === 'number'))
}

function PrimitiveNode({ value }: { value: unknown }) {
  if (value === null) return <span className="cj-null">null</span>
  if (value === undefined) return <span className="cj-null">undefined</span>
  if (typeof value === 'string') return <span className="cj-string">"{value as string}"</span>
  if (typeof value === 'number') return <span className="cj-number">{value as number}</span>
  if (typeof value === 'boolean') return <span className="cj-bool">{String(value)}</span>
  return <span>{String(value)}</span>
}

function CompactArray({ arr, expandLevel, maxPreview }: { arr: unknown[]; expandLevel: number; maxPreview: number }) {
  if (arr.length === 0) return <span className="cj-empty">[]</span>

  // Flat primitive array — compact single line
  if (isFlatArray(arr)) {
    return <span className="cj-line">[{arr.map((v, i) => <span key={i}>{i > 0 ? ', ' : ''}<PrimitiveNode value={v} /></span>)}]</span>
  }

  // Number matrix — each row on one line
  if (isNumberMatrix(arr)) {
    const needsToggle = arr.length > maxPreview
    const rows = needsToggle ? arr.slice(0, maxPreview) : arr
    return (
      <div className="cj-matrix">
        {rows.map((row, i) => (
          <div className="cj-matrix-row" key={i}>
            [{(row as number[]).map((c, j) => <span key={j}>{j > 0 ? ', ' : ''}<PrimitiveNode value={c} /></span>)}]
          </div>
        ))}
        {needsToggle && (
          <details className="cj-details">
            <summary className="cj-summary">… {arr.length - maxPreview} more rows</summary>
            {arr.slice(maxPreview).map((row, i) => (
              <div className="cj-matrix-row" key={i}>
                [{(row as number[]).map((c, j) => <span key={j}>{j > 0 ? ', ' : ''}<PrimitiveNode value={c} /></span>)}]
              </div>
            ))}
          </details>
        )}
      </div>
    )
  }

  // Mixed / object array — collapsible
  const needsToggle = arr.length > maxPreview
  const items = needsToggle ? arr.slice(0, maxPreview) : arr
  return (
    <div className="cj-array">
      {items.map((item, i) => (
        <div className="cj-array-item" key={i}>
          <span className="cj-array-index">{i}</span>
          <CompactValue value={item} expand={expandLevel - 1} maxPreview={maxPreview} />
        </div>
      ))}
      {needsToggle && (
        <details className="cj-details">
          <summary className="cj-summary">… {arr.length - maxPreview} more items</summary>
          {arr.slice(maxPreview).map((item, i) => (
            <div className="cj-array-item" key={i}>
              <span className="cj-array-index">{i + maxPreview}</span>
              <CompactValue value={item} expand={expandLevel - 1} maxPreview={maxPreview} />
            </div>
          ))}
        </details>
      )}
    </div>
  )
}

function CompactObject({ obj, expandLevel, maxPreview }: { obj: Record<string, unknown>; expandLevel: number; maxPreview: number }) {
  const entries = Object.entries(obj)
  if (entries.length === 0) return <span className="cj-empty">{'{}'}</span>

  // All values primitive — compact single line
  if (entries.every(([, v]) => isPrimitive(v))) {
    return (
      <span className="cj-line">{'{ '}{entries.map(([k, v], i) => (
        <span key={k}>{i > 0 ? ', ' : ''}<span className="cj-key">{k}:</span> <PrimitiveNode value={v} /></span>
      ))}{' }'}</span>
    )
  }

  return (
    <div className="cj-object">
      {entries.map(([key, val]) => {
        if (isPrimitive(val)) {
          return (
            <div className="cj-entry" key={key}>
              <span className="cj-key">{key}:</span>
              <span className="cj-value"><PrimitiveNode value={val} /></span>
            </div>
          )
        }
        return (
          <div className="cj-entry cj-entry-nested" key={key}>
            <span className="cj-key">{key}:</span>
            <div className="cj-nested">
              <CompactValue value={val} expand={expandLevel - 1} maxPreview={maxPreview} />
            </div>
          </div>
        )
      })}
    </div>
  )
}

function CompactValue({ value, expand, maxPreview }: { value: unknown; expand: number; maxPreview: number }): ReactNode {
  if (isPrimitive(value)) return <PrimitiveNode value={value} />
  if (Array.isArray(value)) {
    if (expand < 1) {
      return (
        <ToggleBlock label={`[${value.length}]`}>
          <CompactArray arr={value} expandLevel={expand} maxPreview={maxPreview} />
        </ToggleBlock>
      )
    }
    return <CompactArray arr={value} expandLevel={expand} maxPreview={maxPreview} />
  }
  if (typeof value === 'object' && value !== null) {
    const obj = value as Record<string, unknown>
    if (expand < 1) {
      return (
        <ToggleBlock label={`{ ${Object.keys(obj).join(', ')} }`}>
          <CompactObject obj={obj} expandLevel={expand} maxPreview={maxPreview} />
        </ToggleBlock>
      )
    }
    return <CompactObject obj={obj} expandLevel={expand} maxPreview={maxPreview} />
  }
  return <span>{String(value)}</span>
}

function ToggleBlock({ label, children }: { label: string; children: ReactNode }) {
  return (
    <details className="cj-details">
      <summary className="cj-summary">{label}</summary>
      {children}
    </details>
  )
}

export function CompactJson({ value, defaultExpand = 1, label, maxPreview = 10 }: CompactJsonProps) {
  return (
    <div className="compact-json">
      {label && <span className="cj-label">{label}</span>}
      <CompactValue value={value} expand={defaultExpand} maxPreview={maxPreview} />
    </div>
  )
}
