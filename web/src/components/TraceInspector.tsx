import { ArrowRight, Binary, Eye, GitBranch, MousePointer2, ScanSearch } from 'lucide-react'
import type { TraceStep } from '../types'

function TraceBlock({ icon, index, title, children, accent = false }: { icon: React.ReactNode; index: string; title: string; children: React.ReactNode; accent?: boolean }) {
  return (
    <section className={`trace-block ${accent ? 'accent' : ''}`}>
      <div className="trace-block-head"><span>{icon}</span><b>{index}</b><strong>{title}</strong></div>
      <div className="trace-block-body">{children}</div>
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

