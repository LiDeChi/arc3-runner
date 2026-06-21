import { useState } from 'react'

function isPrimitive(value: unknown): boolean {
  return value === null || typeof value === 'boolean' || typeof value === 'number' || typeof value === 'string'
}

function isShortPrimitiveArray(value: unknown): value is (number | string | boolean | null)[] {
  if (!Array.isArray(value)) return false
  if (value.length > 10) return false
  return value.every(isPrimitive)
}

function isNumberMatrix(value: unknown): value is number[][] {
  if (!Array.isArray(value)) return false
  if (value.length === 0) return false
  if (!Array.isArray(value[0])) return false
  return value.every((row) => Array.isArray(row) && row.every((cell) => typeof cell === 'number'))
}



function inlinePrimitiveArray(value: unknown[]): string {
  return `[${value.map(String).join(', ')}]`
}

export function CompactJson({ data, expandDepth = 2, label }: { data: unknown; expandDepth?: number; label?: string }) {
  return (
    <div className="compact-json">
      {label && <div className="compact-json-label">{label}</div>}
      <JsonNode value={data} depth={0} expandDepth={expandDepth} />
    </div>
  )
}

function JsonNode({ value, depth, expandDepth }: { value: unknown; depth: number; expandDepth: number }) {
  if (value === null) return <span className="cj-null">null</span>
  if (typeof value === 'boolean') return <span className="cj-bool">{String(value)}</span>
  if (typeof value === 'number') return <span className="cj-number">{String(value)}</span>
  if (typeof value === 'string') return <span className="cj-string">&quot;{value}&quot;</span>

  if (Array.isArray(value)) {
    if (isShortPrimitiveArray(value)) {
      return <span className="cj-inline-array">{inlinePrimitiveArray(value)}</span>
    }
    if (depth >= expandDepth) {
      return <CollapsibleArray value={value} depth={depth} expandDepth={expandDepth} collapsed={true} />
    }
    return <ArrayBlock value={value} depth={depth} expandDepth={expandDepth} />
  }

  if (typeof value === 'object' && value !== null) {
    if (depth >= expandDepth - 1) {
      return <CollapsibleObject value={value as Record<string, unknown>} depth={depth} expandDepth={expandDepth} collapsed={true} />
    }
    return <ObjectBlock value={value as Record<string, unknown>} depth={depth} expandDepth={expandDepth} />
  }

  return <span>{String(value)}</span>
}

function CollapsibleArray({ value, depth, expandDepth, collapsed: initCollapsed }: { value: unknown[]; depth: number; expandDepth: number; collapsed: boolean }) {
  const [collapsed, setCollapsed] = useState(initCollapsed)
  const total = value.length
  const isMatrix = isNumberMatrix(value)
  const matrixH = isMatrix ? value.length : 0
  const matrixW = isMatrix ? (value[0] as number[]).length : 0

  return (
    <div className="cj-collapsible">
      <button className="cj-toggle" onClick={() => setCollapsed(!collapsed)}>
        <span className={`cj-arrow ${collapsed ? '' : 'expanded'}`}>&#9654;</span>
        <span className="cj-summary">
          {isMatrix
            ? `[${matrixH}×${matrixW} matrix]`
            : `[${total} items]`}
        </span>
      </button>
      {!collapsed && (
        <div className="cj-children">
          {value.map((item, index) => (
            <div className="cj-entry" key={index}>
              <span className="cj-key">{index}: </span>
              <JsonNode value={item} depth={depth + 1} expandDepth={expandDepth + 1} />
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function ArrayBlock({ value, depth, expandDepth }: { value: unknown[]; depth: number; expandDepth: number }) {
  const total = value.length
  const isMatrix = isNumberMatrix(value)

  if (isMatrix) {
    const rows = value as number[][]
    const previewCount = Math.min(6, rows.length)
    return (
      <div className="cj-matrix">
        {rows.slice(0, previewCount).map((row, index) => (
          <div className="cj-matrix-row" key={index}>
            <span className="cj-matrix-idx">{String(index).padStart(2, '0')}:</span>
            <span className="cj-matrix-data">[{row.join(', ')}]</span>
          </div>
        ))}
        {rows.length > previewCount && (
          <div className="cj-matrix-more">··· {rows.length - previewCount} more rows</div>
        )}
      </div>
    )
  }

  const previewCount = Math.min(6, total)
  return (
    <div className="cj-array">
      {value.slice(0, previewCount).map((item, index) => (
        <div className="cj-entry" key={index}>
          <span className="cj-key">{index}: </span>
          <JsonNode value={item} depth={depth + 1} expandDepth={expandDepth} />
        </div>
      ))}
      {total > previewCount && (
        <div className="cj-more">··· {total - previewCount} more items</div>
      )}
    </div>
  )
}

function CollapsibleObject({ value, depth, expandDepth, collapsed: initCollapsed }: { value: Record<string, unknown>; depth: number; expandDepth: number; collapsed: boolean }) {
  const [collapsed, setCollapsed] = useState(initCollapsed)
  const keys = Object.keys(value)
  return (
    <div className="cj-collapsible">
      <button className="cj-toggle" onClick={() => setCollapsed(!collapsed)}>
        <span className={`cj-arrow ${collapsed ? '' : 'expanded'}`}>&#9654;</span>
        <span className="cj-summary">{`{${keys.length} keys}`}</span>
      </button>
      {!collapsed && <ObjectBlock value={value} depth={depth} expandDepth={expandDepth} />}
    </div>
  )
}

function ObjectBlock({ value, depth, expandDepth }: { value: Record<string, unknown>; depth: number; expandDepth: number }) {
  const entries = Object.entries(value)
  const allPrimitive = entries.every(([, v]) => isPrimitive(v))

  if (allPrimitive) {
    return (
      <div className="cj-object-flat">
        {entries.map(([key, val]) => (
          <div className="cj-entry" key={key}>
            <span className="cj-key">{key}: </span>
            <JsonNode value={val} depth={depth + 1} expandDepth={expandDepth} />
          </div>
        ))}
      </div>
    )
  }

  return (
    <div className="cj-object">
      {entries.map(([key, val]) => (
        <div className="cj-entry" key={key}>
          <div className="cj-key-row">
            <span className="cj-key">{key}:</span>
          </div>
          <div className="cj-val">
            <JsonNode value={val} depth={depth + 1} expandDepth={expandDepth} />
          </div>
        </div>
      ))}
    </div>
  )
}
