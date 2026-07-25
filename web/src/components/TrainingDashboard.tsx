import { useEffect, useMemo, useState } from 'react'
import { AlertTriangle, Play, RefreshCw } from 'lucide-react'
import { fetchGenerationEpisodes, fetchTrainingGenerations, startTraining } from '../api'
import type { TrainingEpisodeSummary, TrainingGenerationMetrics, TrainingStartParams } from '../types'
import { CalibrationView } from './CalibrationView'
import { EpisodeReplay } from './EpisodeReplay'
import { KnowledgeView } from './KnowledgeView'
import { TrendChart } from './TrendChart'

type TrainingPanel = 'dashboard' | 'knowledge' | 'calibration'

const metricHelp = {
  solve_rate: '通关率：本代合成题的解出比例。',
  prediction_accuracy: '预测精确度：想象帧与实际帧的平均一致度（1-平均惊奇）。',
  ece: 'ECE：校准误差，agent 声称的把握与实际命中率的差距，越低越好。',
  fool_score: 'fool_score：合成器骗分，骗到高置信预测才得分，越低说明 agent 越难骗。',
}

function percent(value: number): string {
  return `${Math.round(value * 100)}%`
}

export function TrainingDashboard() {
  const [panel, setPanel] = useState<TrainingPanel>('dashboard')
  const [params, setParams] = useState<TrainingStartParams>({
    generations: 10,
    games_per_gen: 12,
    trap_filter: ['T1', 'T6'],
  })
  const [generations, setGenerations] = useState<TrainingGenerationMetrics[]>([])
  const [selectedGen, setSelectedGen] = useState<number | null>(null)
  const [episodes, setEpisodes] = useState<TrainingEpisodeSummary[]>([])
  const [selectedEpisodeId, setSelectedEpisodeId] = useState<string | null>(null)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchTrainingGenerations()
      .then((payload) => {
        setGenerations(payload)
        setSelectedGen(payload.at(-1)?.gen ?? null)
      })
      .catch(() => undefined)
  }, [])

  useEffect(() => {
    if (!selectedGen) return
    fetchGenerationEpisodes(selectedGen)
      .then((payload) => {
        setError(null)
        setEpisodes(payload)
        setSelectedEpisodeId(payload[0]?.episode_id ?? null)
      })
      .catch((reason: Error) => setError(reason.message))
  }, [selectedGen])

  const selectedGeneration = useMemo(
    () => generations.find((item) => item.gen === selectedGen) ?? null,
    [generations, selectedGen],
  )

  const runTraining = async () => {
    setRunning(true)
    setError(null)
    try {
      const payload = await startTraining(params)
      setGenerations(payload)
      setSelectedGen(payload.at(-1)?.gen ?? null)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '训练启动失败')
    } finally {
      setRunning(false)
    }
  }

  const toggleTrap = (trap: string) => {
    setParams((current) => {
      const hasTrap = current.trap_filter.includes(trap)
      const trap_filter = hasTrap
        ? current.trap_filter.filter((item) => item !== trap)
        : [...current.trap_filter, trap]
      return { ...current, trap_filter: trap_filter.length ? trap_filter : [trap] }
    })
  }

  return (
    <section className="training-dashboard">
      <header className="training-header">
        <div>
          <span className="section-label">TRAINING MODE</span>
          <h2>训练可用性工作台</h2>
        </div>
        <div className="training-tabs">
          <button className={panel === 'dashboard' ? 'active' : ''} onClick={() => setPanel('dashboard')}>训练</button>
          <button className={panel === 'knowledge' ? 'active' : ''} onClick={() => setPanel('knowledge')}>知识库</button>
          <button className={panel === 'calibration' ? 'active' : ''} onClick={() => setPanel('calibration')}>校准</button>
        </div>
      </header>

      {panel === 'knowledge' && <KnowledgeView />}
      {panel === 'calibration' && <CalibrationView />}
      {panel === 'dashboard' && (
        <div className="training-grid">
          <aside className="training-control-panel">
            <div className="training-section-head">
              <div>
                <span className="section-label">PARAMS</span>
                <h3>训练参数</h3>
              </div>
            </div>
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
            <div className="trap-picker">
              <span>陷阱类型</span>
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
            <button className="primary-action training-start" onClick={runTraining} disabled={running}>
              {running ? <RefreshCw size={15} className="spin" /> : <Play size={15} />}
              开始训练
            </button>
            {error && <div className="training-error"><AlertTriangle size={13} />{error}</div>}
            {!generations.length && (
              <div className="training-guide-card">
                <strong>三步打开训练黑盒</strong>
                <span>1 设参数</span>
                <span>2 开始训练</span>
                <span>3 点任意世代下钻查看 agent 每一步决策</span>
              </div>
            )}
          </aside>

          <main className="training-main-panel">
            <div className="metric-row">
              <Metric label="通关率" title={metricHelp.solve_rate} value={selectedGeneration ? percent(selectedGeneration.solve_rate) : '—'} />
              <Metric label="预测精确度" title={metricHelp.prediction_accuracy} value={selectedGeneration ? percent(selectedGeneration.prediction_accuracy) : '—'} />
              <Metric label="ECE" title={metricHelp.ece} value={selectedGeneration ? selectedGeneration.ece.toFixed(3) : '—'} />
              <Metric label="fool_score" title={metricHelp.fool_score} value={selectedGeneration ? selectedGeneration.fool_score.toFixed(2) : '—'} />
            </div>

            <div className="training-charts">
              <TrendChart
                title="通关率与预测精确度"
                yDomain={[0, 1]}
                series={[
                  { label: 'solve_rate', color: '#32c787', points: generations.map((item) => ({ x: item.gen, y: item.solve_rate })) },
                  { label: 'prediction_accuracy', color: '#5a86ff', points: generations.map((item) => ({ x: item.gen, y: item.prediction_accuracy })) },
                ]}
              />
              <TrendChart
                title="ECE 与 fool_score"
                subtitle="fool_score / 5 归一化显示"
                yDomain={[0, 1]}
                series={[
                  { label: 'ece', color: '#f2c14e', points: generations.map((item) => ({ x: item.gen, y: item.ece })) },
                  { label: 'fool_score / 5', color: '#ef3340', points: generations.map((item) => ({ x: item.gen, y: Math.min(1, item.fool_score / 5) })) },
                ]}
              />
            </div>

            <div className="training-drilldown">
              <GenerationTable generations={generations} selectedGen={selectedGen} onSelect={setSelectedGen} />
              <EpisodeTable episodes={episodes} selectedEpisodeId={selectedEpisodeId} onSelect={setSelectedEpisodeId} />
            </div>
          </main>

          <EpisodeReplay episodeId={selectedEpisodeId} />
        </div>
      )}
    </section>
  )
}

function Metric({ label, title, value }: { label: string; title: string; value: string }) {
  return (
    <div className="metric-card" title={title}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  )
}

function GenerationTable({
  generations,
  selectedGen,
  onSelect,
}: {
  generations: TrainingGenerationMetrics[]
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
            <span>{percent(generation.solve_rate)}</span>
            <span>{percent(generation.prediction_accuracy)}</span>
            <span>{generation.ece.toFixed(3)}</span>
            <strong>{generation.fool_score.toFixed(2)}</strong>
            <code>{Object.entries(generation.weights).map(([key, value]) => `${key}:${value}`).join(' ')}</code>
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
