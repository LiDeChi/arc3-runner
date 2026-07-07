import type { TraceStep } from '../types'
import { PixelGrid } from './PixelGrid'

interface ImaginationViewProps {
  step: TraceStep
}

export function ImaginationView({ step }: ImaginationViewProps) {
  const imagination = step.imagination

  return (
    <div className="diff-layout">
      <div className="diff-view">
        <div><span>BEFORE</span><PixelGrid frame={step.before_frame ?? step.frame} label="动作前帧" /></div>
        <div>
          <span>IMAGINED</span>
          <PixelGrid frame={imagination?.predicted_frame ?? step.before_frame ?? step.frame} label="想象帧" />
        </div>
        <div><span>ACTUAL</span><PixelGrid frame={step.frame} beforeFrame={imagination?.predicted_frame} showDiff label="实际帧" /></div>
      </div>
      <section className="data-section">
        <div className="data-section-head">
          <strong>惊奇与规划树</strong>
          <span>{imagination?.mode?.toUpperCase() ?? 'NO DATA'}</span>
        </div>
        <div className="data-section-body">
          <pre className="json-panel">{JSON.stringify({ surprise: step.surprise, plan_tree: imagination?.plan_tree ?? null }, null, 2)}</pre>
        </div>
      </section>
    </div>
  )
}
