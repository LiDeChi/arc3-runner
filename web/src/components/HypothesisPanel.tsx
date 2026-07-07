import type { TraceStep } from '../types'
import { VectorFieldOverlay } from './VectorFieldOverlay'

interface HypothesisPanelProps {
  step: TraceStep
}

export function HypothesisPanel({ step }: HypothesisPanelProps) {
  const hypotheses = step.hypotheses ?? []
  const credibility = step.credibility

  return (
    <div className="data-grid decision-grid">
      <section className="data-section">
        <div className="data-section-head">
          <strong>动作变换假设</strong>
          <span>{hypotheses.length} HYPOTHESES</span>
        </div>
        <div className="data-section-body">
          <div className="compact-table hypothesis-table">
            <div className="compact-head">
              <span>ACTION</span>
              <span>READABLE</span>
              <span>VECTOR</span>
              <span>CONF</span>
              <span>SUPPORT</span>
              <span>ALT</span>
            </div>
            {hypotheses.length ? hypotheses.map((item) => (
              <div className="compact-row" key={item.hypothesis_id}>
                <b>ACTION{item.action_id}</b>
                <span>{item.readable}</span>
                <VectorFieldOverlay transform={item.transform} />
                <strong>{Math.round(item.confidence * 100)}%</strong>
                <span>{item.support}/{item.support + item.violations}</span>
                <code>{item.alternatives.join(' | ') || '—'}</code>
              </div>
            )) : <div className="empty-row">尚未形成变换假设</div>}
          </div>
        </div>
      </section>
      <section className="data-section">
        <div className="data-section-head">
          <strong>可信度门控</strong>
          <span>{credibility?.gate?.toUpperCase() ?? 'NO DATA'}</span>
        </div>
        <div className="data-section-body">
          <pre className="json-panel">{JSON.stringify(credibility ?? { claimed: 0, calibrated: 0, gate: 'probe' }, null, 2)}</pre>
        </div>
      </section>
    </div>
  )
}
