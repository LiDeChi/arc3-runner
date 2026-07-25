import type { TraceStep } from '../types'
import { PixelGrid } from './PixelGrid'

interface ImaginationViewProps {
  step: TraceStep
}

export function ImaginationView({ step }: ImaginationViewProps) {
  const before = step.imagination?.before_frame ?? step.before_frame ?? step.frame
  const predicted = step.imagination?.predicted_frame
  const actual = step.imagination?.actual_frame ?? step.frame
  const errors = step.imagination?.error_pixels?.length ?? step.surprise?.predicted_error_pixels ?? 0

  return (
    <section className="imagination-view">
      <div className="imagination-frame">
        <span>BEFORE</span>
        <PixelGrid frame={before ?? step.frame} label={`第 ${step.index} 步动作前帧`} />
      </div>
      <div className="imagination-frame">
        <span>IMAGINED</span>
        {predicted ? (
          <PixelGrid frame={predicted} label={`第 ${step.index} 步想象帧`} />
        ) : (
          <div className="imagination-empty">无预测帧</div>
        )}
      </div>
      <div className="imagination-frame">
        <span>ACTUAL · {errors} px error</span>
        <PixelGrid frame={actual} beforeFrame={predicted ?? before} showDiff={Boolean(predicted)} label={`第 ${step.index} 步实际帧`} />
      </div>
    </section>
  )
}
