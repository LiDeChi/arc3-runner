export interface TrendPoint {
  x: number
  y: number
}

export interface TrendSeries {
  label: string
  color: string
  points: TrendPoint[]
}

interface TrendChartProps {
  title: string
  subtitle?: string
  series: TrendSeries[]
  yDomain?: [number, number]
}

function extent(series: TrendSeries[]): [number, number] {
  const values = series.flatMap((item) => item.points.map((point) => point.y))
  if (!values.length) return [0, 1]
  const min = Math.min(...values)
  const max = Math.max(...values)
  if (min === max) return [Math.min(0, min), Math.max(1, max)]
  return [min, max]
}

function pathFor(points: TrendPoint[], xScale: (x: number) => number, yScale: (y: number) => number): string {
  return points
    .map((point, index) => `${index === 0 ? 'M' : 'L'}${xScale(point.x).toFixed(1)} ${yScale(point.y).toFixed(1)}`)
    .join(' ')
}

export function TrendChart({ title, subtitle, series, yDomain }: TrendChartProps) {
  const width = 520
  const height = 190
  const pad = { left: 34, right: 16, top: 18, bottom: 28 }
  const allX = series.flatMap((item) => item.points.map((point) => point.x))
  const labelXs = Array.from(new Set(allX)).filter((x, index, values) => {
    const stride = Math.max(1, Math.ceil(values.length / 8))
    return index === 0 || index === values.length - 1 || index % stride === 0
  })
  const xMin = allX.length ? Math.min(...allX) : 0
  const xMax = allX.length ? Math.max(...allX) : 1
  const [rawMin, rawMax] = yDomain ?? extent(series)
  const yMin = yDomain ? rawMin : Math.min(0, rawMin)
  const yMax = yDomain ? rawMax : Math.max(1, rawMax)
  const xScale = (x: number) => pad.left + ((x - xMin) / Math.max(1, xMax - xMin)) * (width - pad.left - pad.right)
  const yScale = (y: number) => height - pad.bottom - ((y - yMin) / Math.max(0.001, yMax - yMin)) * (height - pad.top - pad.bottom)
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((ratio) => yMin + ratio * (yMax - yMin))

  return (
    <section className="trend-card">
      <div className="trend-head">
        <div>
          <strong>{title}</strong>
          {subtitle && <span>{subtitle}</span>}
        </div>
        <div className="trend-legend">
          {series.map((item) => <span key={item.label}><i style={{ background: item.color }} />{item.label}</span>)}
        </div>
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} className="trend-chart" role="img" aria-label={title}>
        {ticks.map((tick) => (
          <g key={tick}>
            <line x1={pad.left} x2={width - pad.right} y1={yScale(tick)} y2={yScale(tick)} />
            <text x={pad.left - 8} y={yScale(tick) + 3}>{tick.toFixed(yMax <= 1 ? 2 : 1)}</text>
          </g>
        ))}
        {labelXs.map((x) => (
          <text key={x} x={xScale(x)} y={height - 8} className="x-label">{x}</text>
        ))}
        {series.map((item) => (
          <g key={item.label}>
            <path d={pathFor(item.points, xScale, yScale)} style={{ stroke: item.color }} />
            {item.points.map((point) => (
              <circle key={`${item.label}-${point.x}`} cx={xScale(point.x)} cy={yScale(point.y)} r={3.2} style={{ fill: item.color }}>
                <title>{`${item.label} gen ${point.x}: ${point.y.toFixed(3)}`}</title>
              </circle>
            ))}
          </g>
        ))}
      </svg>
    </section>
  )
}
