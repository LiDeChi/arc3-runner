import { PauseCircle, Play, RefreshCw } from 'lucide-react'
import type { TrainingGeneration, TrainingStatus } from '../types'

interface TrainingDashboardProps {
  status?: TrainingStatus
  generations: TrainingGeneration[]
  loading: boolean
  onStart: () => void
  onStop: () => void
  onRefresh: () => void
}

export function TrainingDashboard({
  status,
  generations,
  loading,
  onStart,
  onStop,
  onRefresh,
}: TrainingDashboardProps) {
  const latest = generations.at(-1)
  const running = status?.status === 'running' || status?.status === 'stopping'
  const officialEval = latest?.gen_metrics.official_eval as {
    summary?: Record<string, Record<string, number>>
    delta?: Record<string, number>
    trained_delta?: Record<string, number>
    game_count?: number
  } | undefined
  return (
    <section className="training-dashboard">
      <div className="training-panel-head">
        <div>
          <span className="section-label">TRAINING / DASHBOARD</span>
          <h2>训练总览</h2>
        </div>
        <div className="training-actions">
          <button onClick={onStart} disabled={running}><Play size={12} />开始 3×4</button>
          <button onClick={onStop} disabled={!running}><PauseCircle size={12} />停止</button>
          <button onClick={onRefresh} disabled={loading}><RefreshCw size={12} className={loading ? 'spin' : ''} />刷新</button>
        </div>
      </div>

      <div className="training-metric-grid">
        <Metric label="状态" value={status?.status ?? 'idle'} />
        <Metric label="世代" value={`${status?.current_generation ?? 0}/${status?.total_generations ?? 0}`} />
        <Metric label="本代局数" value={`${status?.games_completed ?? 0}/${status?.games_per_generation ?? 0}`} />
        <Metric label="当前题" value={status?.current_game ?? '—'} wide />
      </div>

      <div className="training-chart-grid">
        <div className="training-chart">
          <h3>通关率 / 预测精确度</h3>
          <TrendRows generations={generations} fields={['solve_rate', 'prediction_accuracy']} source="agent_metrics" />
        </div>
        <div className="training-chart">
          <h3>校准误差 / fool_score</h3>
          <TrendRows generations={generations} fields={['ece', 'fool_score']} source="mixed" />
        </div>
      </div>

      <div className="training-live-strip">
        <span>latest</span>
        <b>{latest ? `gen ${latest.gen}` : 'no generations yet'}</b>
        <em>{latest ? `weights ${Object.entries(latest.weights).map(([k, v]) => `${k}:${Number(v).toFixed(2)}`).join(' · ')}` : 'start training to populate SQLite'}</em>
      </div>

      {officialEval && (
        <div className="official-eval-card">
          <h3>官方环境对照评测</h3>
          <div className="official-eval-grid">
            <Metric label="games" value={officialEval.game_count ?? 0} />
            <Metric label="raw Δ solve" value={Number(officialEval.delta?.solve_rate ?? 0).toFixed(3)} />
            <Metric label="raw Δ acc" value={Number(officialEval.delta?.prediction_accuracy ?? 0).toFixed(3)} />
            <Metric label="raw Δ ece" value={Number(officialEval.delta?.ece ?? 0).toFixed(3)} />
            <Metric label="trained Δ solve" value={Number(officialEval.trained_delta?.solve_rate ?? 0).toFixed(3)} />
            <Metric label="trained Δ acc" value={Number(officialEval.trained_delta?.prediction_accuracy ?? 0).toFixed(3)} />
            <Metric label="trained Δ ece" value={Number(officialEval.trained_delta?.ece ?? 0).toFixed(3)} />
          </div>
        </div>
      )}
    </section>
  )
}

function Metric({ label, value, wide = false }: { label: string; value: string | number; wide?: boolean }) {
  return (
    <div className={`training-metric ${wide ? 'wide' : ''}`}>
      <span>{label}</span>
      <b>{value}</b>
    </div>
  )
}

function TrendRows({
  generations,
  fields,
  source,
}: {
  generations: TrainingGeneration[]
  fields: string[]
  source: 'agent_metrics' | 'mixed'
}) {
  if (!generations.length) return <p className="training-empty">还没有训练世代。</p>
  return (
    <div className="trend-rows">
      {fields.map((field) => (
        <div className="trend-row" key={field}>
          <span>{field}</span>
          <div>
            {generations.map((generation) => {
              const raw = source === 'agent_metrics' || field !== 'fool_score'
                ? generation.agent_metrics[field]
                : generation.gen_metrics[field]
              const value = Number(raw ?? 0)
              return <i key={`${generation.gen}-${field}`} style={{ height: `${Math.max(4, Math.min(100, value * 100))}%` }} title={`gen ${generation.gen}: ${value}`} />
            })}
          </div>
          <b>{Number((source === 'agent_metrics' || field !== 'fool_score' ? generations.at(-1)?.agent_metrics[field] : generations.at(-1)?.gen_metrics[field]) ?? 0).toFixed(3)}</b>
        </div>
      ))}
    </div>
  )
}
