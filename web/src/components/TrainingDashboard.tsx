import { useEffect, useMemo, useState } from 'react'
import { AlertTriangle, PauseCircle, Play, RefreshCw } from 'lucide-react'
import { fetchTrainingGenerationEpisodes } from '../api'
import type {
  TrainingEpisodeSummary,
  TrainingGeneration,
  TrainingStartParams,
  TrainingStatus,
} from '../types'
import { EpisodeReplay } from './EpisodeReplay'
import { TrendChart } from './TrendChart'

interface TrainingDashboardProps {
  status?: TrainingStatus
  generations: TrainingGeneration[]
  loading: boolean
  onStart: (params: TrainingStartParams) => void | Promise<void>
  onStop: () => void
  onRefresh: () => void
}

function agentMetric(generation: TrainingGeneration, field: string): number {
  return Number(generation.agent_metrics[field] ?? 0)
}

function foolScore(generation: TrainingGeneration): number {
  return Number(generation.gen_metrics.fool_score ?? 0)
}

function percent(value: number): string {
  return `${Math.round(value * 100)}%`
}

export function TrainingDashboard({
  status,
  generations,
  loading,
  onStart,
  onStop,
  onRefresh,
}: TrainingDashboardProps) {
  const [params, setParams] = useState<TrainingStartParams>({
    generations: 3,
    games_per_gen: 4,
    trap_filter: ['T1', 'T6'],
  })
  const [selectedGen, setSelectedGen] = useState<number | null>(null)
  const [episodes, setEpisodes] = useState<TrainingEpisodeSummary[]>([])
  const [selectedEpisodeId, setSelectedEpisodeId] = useState<string | null>(null)
  const [drilldownError, setDrilldownError] = useState<string | null>(null)

  const latest = generations.at(-1)
  const running = status?.status === 'running' || status?.status === 'stopping'
  const activeGen = generations.some((generation) => generation.gen === selectedGen)
    ? selectedGen
    : latest?.gen ?? null
  const selectedGeneration = useMemo(
    () => generations.find((generation) => generation.gen === activeGen) ?? latest,
    [activeGen, generations, latest],
  )
  const officialEval = latest?.gen_metrics.official_eval as {
    summary?: Record<string, Record<string, number>>
    delta?: Record<string, number>
    trained_delta?: Record<string, number>
    game_count?: number
  } | undefined

  useEffect(() => {
    if (activeGen === null) return
    fetchTrainingGenerationEpisodes(activeGen)
      .then((payload) => {
        setDrilldownError(null)
        setEpisodes(payload)
        setSelectedEpisodeId((current) => (
          payload.some((episode) => episode.episode_id === current)
            ? current
            : payload[0]?.episode_id ?? null
        ))
      })
      .catch((reason: Error) => {
        setEpisodes([])
        setSelectedEpisodeId(null)
        setDrilldownError(reason.message)
      })
  }, [activeGen, generations])

  const toggleTrap = (trap: string) => {
    setParams((current) => {
      const selected = current.trap_filter.includes(trap)
      const trapFilter = selected
        ? current.trap_filter.filter((item) => item !== trap)
        : [...current.trap_filter, trap]
      return { ...current, trap_filter: trapFilter.length ? trapFilter : [trap] }
    })
  }

  return (
    <section className="training-dashboard">
      <div className="training-panel-head">
        <div>
          <span className="section-label">TRAINING / DASHBOARD</span>
          <h2>训练总览与逐步回放</h2>
        </div>
        <div className="training-actions">
          <button onClick={() => onStart(params)} disabled={running || loading}><Play size={12} />开始训练</button>
          <button onClick={onStop} disabled={!running}><PauseCircle size={12} />停止</button>
          <button onClick={onRefresh} disabled={loading}><RefreshCw size={12} className={loading ? 'spin' : ''} />刷新</button>
        </div>
      </div>

      <div className="training-params">
        <label>
          世代数
          <input
            type="number"
            min={1}
            max={50}
            value={params.generations}
            onChange={(event) => setParams({ ...params, generations: Number(event.target.value) })}
          />
        </label>
        <label>
          每代局数
          <input
            type="number"
            min={1}
            max={50}
            value={params.games_per_gen}
            onChange={(event) => setParams({ ...params, games_per_gen: Number(event.target.value) })}
          />
        </label>
        <div className="training-traps">
          <span>陷阱</span>
          {['T1', 'T6'].map((trap) => (
            <button
              key={trap}
              className={params.trap_filter.includes(trap) ? 'active' : ''}
              onClick={() => toggleTrap(trap)}
            >
              {trap}
            </button>
          ))}
        </div>
      </div>

      <div className="training-metric-grid">
        <Metric label="状态" value={status?.status ?? 'idle'} />
        <Metric label="世代" value={`${status?.current_generation ?? 0}/${status?.total_generations ?? 0}`} />
        <Metric label="本代局数" value={`${status?.games_completed ?? 0}/${status?.games_per_generation ?? 0}`} />
        <Metric label="当前题" value={status?.current_game ?? '—'} wide />
      </div>

      <div className="training-chart-grid">
        <TrendChart
          title="通关率与预测精确度"
          yDomain={[0, 1]}
          series={[
            {
              label: 'solve_rate',
              color: '#32c787',
              points: generations.map((generation) => ({ x: generation.gen, y: agentMetric(generation, 'solve_rate') })),
            },
            {
              label: 'prediction_accuracy',
              color: '#5a86ff',
              points: generations.map((generation) => ({ x: generation.gen, y: agentMetric(generation, 'prediction_accuracy') })),
            },
          ]}
        />
        <TrendChart
          title="ECE 与 fool_score"
          subtitle="fool_score / 5 归一化显示"
          yDomain={[0, 1]}
          series={[
            {
              label: 'ece',
              color: '#f2c14e',
              points: generations.map((generation) => ({ x: generation.gen, y: agentMetric(generation, 'ece') })),
            },
            {
              label: 'fool_score / 5',
              color: '#ef3340',
              points: generations.map((generation) => ({ x: generation.gen, y: Math.min(1, foolScore(generation) / 5) })),
            },
          ]}
        />
      </div>

      <div className="training-drilldown">
        <GenerationTable generations={generations} selectedGen={selectedGeneration?.gen ?? null} onSelect={setSelectedGen} />
        <EpisodeTable episodes={episodes} selectedEpisodeId={selectedEpisodeId} onSelect={setSelectedEpisodeId} />
      </div>
      {drilldownError && <div className="training-error"><AlertTriangle size={13} />{drilldownError}</div>}

      <EpisodeReplay episodeId={activeGen === null ? null : selectedEpisodeId} />

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

function GenerationTable({
  generations,
  selectedGen,
  onSelect,
}: {
  generations: TrainingGeneration[]
  selectedGen: number | null
  onSelect: (gen: number) => void
}) {
  return (
    <section className="training-table-panel">
      <div className="training-section-head"><h3>世代</h3><span>{generations.length} GEN</span></div>
      <div className="compact-table generation-table">
        <div className="compact-head"><span>GEN</span><span>SOLVE</span><span>ACC</span><span>ECE</span><span>FOOL</span><span>WEIGHTS</span></div>
        {generations.map((generation) => (
          <button
            className={`compact-row ${generation.gen === selectedGen ? 'chosen-row' : ''}`}
            key={generation.gen}
            onClick={() => onSelect(generation.gen)}
          >
            <b>{generation.gen}</b>
            <span>{percent(agentMetric(generation, 'solve_rate'))}</span>
            <span>{percent(agentMetric(generation, 'prediction_accuracy'))}</span>
            <span>{agentMetric(generation, 'ece').toFixed(3)}</span>
            <strong>{foolScore(generation).toFixed(2)}</strong>
            <code>{Object.entries(generation.weights).map(([key, value]) => `${key}:${Number(value).toFixed(2)}`).join(' ')}</code>
          </button>
        ))}
      </div>
    </section>
  )
}

function EpisodeTable({
  episodes,
  selectedEpisodeId,
  onSelect,
}: {
  episodes: TrainingEpisodeSummary[]
  selectedEpisodeId: string | null
  onSelect: (episodeId: string) => void
}) {
  return (
    <section className="training-table-panel">
      <div className="training-section-head"><h3>Episodes</h3><span>{episodes.length} RUNS</span></div>
      <div className="compact-table episode-table">
        <div className="compact-head"><span>TRAP</span><span>SOLVED</span><span>FOOL</span><span>MAX S</span><span>STEPS</span></div>
        {episodes.map((episode) => (
          <button
            className={`compact-row ${episode.episode_id === selectedEpisodeId ? 'chosen-row' : ''} ${episode.max_surprise >= 0.3 ? 'surprise-row-hot' : ''}`}
            key={episode.episode_id}
            onClick={() => onSelect(episode.episode_id)}
          >
            <b>{episode.trap}</b>
            <span>{episode.solved ? '✓' : '✗'}</span>
            <strong>{episode.fool_score.toFixed(2)}</strong>
            <span>{episode.max_surprise.toFixed(2)}</span>
            <span>{episode.steps}</span>
          </button>
        ))}
      </div>
    </section>
  )
}
