import type { TrainingGeneration, TrainingKnowledge } from '../types'

export function CalibrationView({ knowledge, generations }: { knowledge?: TrainingKnowledge; generations: TrainingGeneration[] }) {
  const calibration = knowledge?.calibration ?? []
  return (
    <section className="training-dashboard">
      <div className="training-panel-head">
        <div>
          <span className="section-label">TRAINING / CALIBRATION</span>
          <h2>可信度</h2>
        </div>
      </div>
      <div className="calibration-grid">
        <div className="training-chart calibration-panel">
          <h3>Reliability Diagram</h3>
          {calibration.length ? calibration.map((bucket) => (
            <div className="calibration-row" key={bucket.bucket}>
              <span>{Number(bucket.claimed).toFixed(2)}</span>
              <i><b style={{ width: `${Math.min(100, Number(bucket.hit_rate) * 100)}%` }} /></i>
              <em>{Number(bucket.hit_rate).toFixed(2)} · n={bucket.n}</em>
            </div>
          )) : <p className="training-empty">训练后会显示声称置信度与实际命中率。</p>}
        </div>
        <div className="training-chart calibration-panel">
          <h3>逐代 ECE</h3>
          <div className="trend-rows">
            <div className="trend-row">
              <span>ece</span>
              <div>
                {generations.map((generation) => (
                  <i key={generation.gen} style={{ height: `${Math.max(4, Number(generation.agent_metrics.ece ?? 0) * 100)}%` }} />
                ))}
              </div>
              <b>{Number(generations.at(-1)?.agent_metrics.ece ?? 0).toFixed(3)}</b>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
