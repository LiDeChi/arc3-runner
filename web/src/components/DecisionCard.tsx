import { AlertTriangle, BrainCircuit, GitBranch } from 'lucide-react'
import type { TraceStep, TransformHypothesis } from '../types'
import { VectorFieldOverlay } from './VectorFieldOverlay'

interface DecisionCardProps {
  step: TraceStep
  compact?: boolean
}

function percent(value: number | undefined): string {
  if (value === undefined || Number.isNaN(value)) return '—'
  return `${Math.round(Math.max(0, Math.min(1, value)) * 100)}%`
}

function selectedHypothesis(step: TraceStep): TransformHypothesis | undefined {
  return step.hypotheses?.find((hypothesis) => hypothesis.action_id === step.action_id)
    ?? step.hypotheses?.[0]
}

function gateLabel(step: TraceStep): { label: string; className: string } {
  const gate = step.credibility?.gate
    ?? (step.index === 0
      ? 'reset'
      : step.selected_reason.toLowerCase().includes('exploit') ? 'exploit' : 'probe')
  if (gate === 'exploit') return { label: 'EXPLOIT', className: 'exploit' }
  if (gate === 'probe') return { label: 'PROBE', className: 'probe' }
  return { label: 'RESET', className: 'reset' }
}

function beliefFlipLabel(value: { from: string; to: string }): string {
  return `${value.from} → ${value.to}`
}

export function DecisionCard({ step, compact = false }: DecisionCardProps) {
  const hypothesis = selectedHypothesis(step)
  const gate = gateLabel(step)
  const claimed = step.credibility?.claimed ?? hypothesis?.confidence
  const calibrated = step.credibility?.calibrated ?? claimed
  const surpriseValue = step.surprise?.value ?? 0
  const surpriseHot = surpriseValue >= 0.3
  const predictedError = step.surprise?.pixel_error ?? 0

  return (
    <section className={`decision-card ${compact ? 'compact' : ''} ${surpriseHot ? 'surprised' : ''}`}>
      <div className="decision-head">
        <div className="decision-head-left">
          <span className="decision-title">本步决策</span>
          <span className={`decision-gate ${gate.className}`}>{gate.label}</span>
        </div>
        <strong>选择 {step.action_name}</strong>
      </div>
      <div className="decision-main">
        {hypothesis && <VectorFieldOverlay transform={hypothesis.transform} />}
        <code>{hypothesis?.readable ?? step.hypothesis ?? '尚未形成变换假设'}</code>
      </div>
      <div className="confidence-row">
        <span>置信</span>
        <div className="confidence-track">
          <i className="claimed" style={{ width: percent(claimed) }} />
          <i className="calibrated" style={{ width: percent(calibrated) }} />
        </div>
        <b>{percent(claimed)}</b>
        <em>校准后 {percent(calibrated)}</em>
      </div>
      <div className={`surprise-row ${surpriseHot ? 'hot' : ''}`}>
        {surpriseHot && <AlertTriangle size={12} />}
        <span>惊奇 {surpriseValue.toFixed(2)} · {predictedError} px 预测误差</span>
      </div>
      {step.selected_reason && <p className="decision-reason">理由：{step.selected_reason}</p>}
      {step.surprise?.belief_flips?.length ? (
        <div className="belief-flips">
          <GitBranch size={12} />
          <span>{step.surprise.belief_flips.map(beliefFlipLabel).join('；')}</span>
        </div>
      ) : null}

      {!compact && (
        <div className="hypothesis-mini-table">
          <div className="hypothesis-mini-head">
            <BrainCircuit size={12} />
            <span>全部动作假设</span>
          </div>
          <div className="hypothesis-mini-grid">
            <span>ACTION</span>
            <span>VECTOR</span>
            <span>函数</span>
            <span>CONF</span>
            <span>SUPPORT</span>
            {(step.hypotheses ?? []).map((item) => (
              <div
                className={`hypothesis-mini-row ${item.action_id === step.action_id ? 'selected' : ''}`}
                key={item.hypothesis_id}
              >
                <b>ACTION{item.action_id}</b>
                <VectorFieldOverlay transform={item.transform} />
                <code title={item.alternatives.join(' / ')}>{item.readable}</code>
                <span>{percent(item.confidence)}</span>
                <span>{item.support}/{item.support + item.violations}</span>
              </div>
            ))}
            {!(step.hypotheses?.length) && <div className="hypothesis-empty">本步没有逐动作函数假设。</div>}
          </div>
        </div>
      )}
    </section>
  )
}
