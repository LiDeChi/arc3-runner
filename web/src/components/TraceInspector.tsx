import { ArrowRight, Binary, Eye, GitBranch, MousePointer2, ScanSearch } from 'lucide-react'
import type { TraceStep, TransformHypothesis } from '../types'
import { readableTransform } from '../utils/transform'

function TraceBlock({ icon, index, title, children, accent = false }: { icon: React.ReactNode; index: string; title: string; children: React.ReactNode; accent?: boolean }) {
  return (
    <section className={`trace-block ${accent ? 'accent' : ''}`}>
      <div className="trace-block-head"><span>{icon}</span><b>{index}</b><strong>{title}</strong></div>
      <div className="trace-block-body">{children}</div>
    </section>
  )
}

function selectedHypothesis(step: TraceStep): TransformHypothesis | undefined {
  return step.hypotheses?.find((hypothesis) => hypothesis.action_id === step.action_id)
    ?? step.hypotheses?.find((hypothesis) => hypothesis.action === step.action_name)
    ?? step.hypotheses?.[0]
}

function percent(value: number | undefined): string {
  if (value === undefined || Number.isNaN(value)) return '—'
  return `${Math.round(Math.max(0, Math.min(1, value)) * 100)}%`
}

function PipelineRow({ token, fn, value }: { token: string; fn: string; value: string }) {
  return (
    <div className="function-row">
      <b>{token}</b>
      <code>{fn}</code>
      <span>{value}</span>
    </div>
  )
}

function FunctionPipeline({ step }: { step: TraceStep }) {
  const hypothesis = selectedHypothesis(step)
  const transform = hypothesis?.readable ?? readableTransform(hypothesis?.transform)
  const predictedError = step.surprise?.predicted_error_pixels ?? step.imagination?.error_pixels?.length ?? 0
  const confidence = step.credibility?.calibrated ?? hypothesis?.calibrated_confidence ?? hypothesis?.confidence

  return (
    <section className="function-pipeline">
      <div className="function-pipeline-head">
        <span>FUNCTIONAL TRACE</span>
        <strong>函数式推理</strong>
      </div>
      <div className="function-chain">
        <PipelineRow
          token="x"
          fn="frame_t, action_space"
          value={`${step.perception.width}×${step.perception.height} · ${step.available_actions.length} actions`}
        />
        <PipelineRow
          token="φ"
          fn="perceive(x)"
          value={`${step.perception.components.length} objects · Δ ${step.changed_cells}`}
        />
        <PipelineRow
          token="H"
          fn="map(a => f_a)"
          value={hypothesis ? `${hypothesis.action}: ${transform}` : 'no transform hypothesis'}
        />
        <PipelineRow
          token="ŷ"
          fn="f_selected(frame_t)"
          value={`${predictedError} px error · S ${(step.surprise?.value ?? 0).toFixed(2)}`}
        />
        <PipelineRow
          token="π"
          fn="argmax(score, conf)"
          value={`${step.action_name} · conf ${percent(confidence)}`}
        />
      </div>
    </section>
  )
}

export function TraceInspector({ step }: { step?: TraceStep }) {
  if (!step) {
    return <aside className="inspector empty-state">等待环境返回首帧…</aside>
  }
  return (
    <aside className="inspector">
      <div className="inspector-header">
        <div><span className="section-label">STEP TRACE</span><strong>决策审计</strong></div>
        <span className="latency">{step.duration_ms} ms</span>
      </div>
      <div className="trace-flow">
        <FunctionPipeline step={step} />
        <TraceBlock icon={<Eye size={14} />} index="01" title="观察">
          <p>{step.observation}</p>
        </TraceBlock>
        <TraceBlock icon={<ScanSearch size={14} />} index="02" title="帧差异">
          <p>{step.detected_change}</p>
          <div className="metric-line"><span>changed cells</span><b>{step.changed_cells}</b></div>
        </TraceBlock>
        <TraceBlock icon={<GitBranch size={14} />} index="03" title="工作假设">
          <p>{step.hypothesis}</p>
        </TraceBlock>
        <TraceBlock icon={<Binary size={14} />} index="04" title="候选动作">
          {step.candidates.length ? (
            <div className="candidate-list">
              {step.candidates.slice(0, 4).map((candidate, index) => (
                <div className="candidate" key={candidate.action}>
                  <span>{String(index + 1).padStart(2, '0')}</span>
                  <b>{candidate.action}</b>
                  <i style={{ width: `${Math.min(100, candidate.score * 28)}%` }} />
                  <em>{candidate.score.toFixed(2)}</em>
                </div>
              ))}
            </div>
          ) : <p>RESET 不需要候选动作。</p>}
        </TraceBlock>
        <TraceBlock icon={<MousePointer2 size={14} />} index="05" title="执行动作" accent>
          <div className="selected-action">
            <strong>{step.action_name}</strong>
            {Object.keys(step.action_data).length > 0 && <code>{JSON.stringify(step.action_data)}</code>}
          </div>
          <p>{step.selected_reason}</p>
        </TraceBlock>
        <div className="result-line"><ArrowRight size={14} /><span>{step.result}</span></div>
      </div>
      <div className="audit-note">{step.audit_note}</div>
    </aside>
  )
}
