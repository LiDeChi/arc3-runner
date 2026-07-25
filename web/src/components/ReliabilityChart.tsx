import type { TrainingKnowledge } from '../types'

interface ReliabilityChartProps {
  points: TrainingKnowledge['calibration']
  title?: string
}

export function ReliabilityChart({ points, title = '校准可靠性' }: ReliabilityChartProps) {
  const width = 360
  const height = 250
  const pad = 34
  const scale = (value: number) => pad + Math.max(0, Math.min(1, value)) * (width - pad * 2)
  const yScale = (value: number) => height - pad - Math.max(0, Math.min(1, value)) * (height - pad * 2)

  return (
    <section className="reliability-card">
      <div className="trend-head">
        <div>
          <strong>{title}</strong>
          <span>虚线 y=x 是完美校准参照</span>
        </div>
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} className="reliability-chart" role="img" aria-label={title}>
        {[0, 0.25, 0.5, 0.75, 1].map((tick) => (
          <g key={tick}>
            <line x1={pad} x2={width - pad} y1={yScale(tick)} y2={yScale(tick)} />
            <line x1={scale(tick)} x2={scale(tick)} y1={pad} y2={height - pad} />
            <text x={pad - 8} y={yScale(tick) + 3}>{tick.toFixed(2)}</text>
            <text x={scale(tick)} y={height - 10} className="x-label">{tick.toFixed(2)}</text>
          </g>
        ))}
        <path className="perfect-line" d={`M${pad} ${height - pad} L${width - pad} ${pad}`} />
        {points.length > 1 && (
          <path
            className="reliability-line"
            d={points.map((point, index) => `${index === 0 ? 'M' : 'L'}${scale(point.claimed)} ${yScale(point.hit_rate)}`).join(' ')}
          />
        )}
        {points.map((point) => (
          <circle
            key={`${point.bucket}-${point.n}`}
            cx={scale(point.claimed)}
            cy={yScale(point.hit_rate)}
            r={Math.max(3, Math.min(11, 2 + point.n / 3))}
          >
            <title>{`claimed ${point.claimed.toFixed(2)} / hit ${point.hit_rate.toFixed(2)} / n ${point.n}`}</title>
          </circle>
        ))}
      </svg>
    </section>
  )
}
