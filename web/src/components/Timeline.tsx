import { Pause, Play, RotateCcw, SkipBack, SkipForward } from 'lucide-react'
import type { TraceStep } from '../types'

interface TimelineProps {
  steps: TraceStep[]
  selectedIndex: number
  playing: boolean
  speed: number
  onPlaying: (value: boolean) => void
  onSelect: (index: number) => void
  onSpeed: (speed: number) => void
}

export function Timeline({ steps, selectedIndex, playing, speed, onPlaying, onSelect, onSpeed }: TimelineProps) {
  const selected = steps[selectedIndex]
  return (
    <section className="timeline-panel">
      <div className="transport">
        <button aria-label="回到首帧" onClick={() => onSelect(0)}><RotateCcw size={14} /></button>
        <button aria-label="上一帧" onClick={() => onSelect(Math.max(0, selectedIndex - 1))}><SkipBack size={14} /></button>
        <button className="play-button" aria-label={playing ? '暂停' : '播放'} onClick={() => onPlaying(!playing)}>
          {playing ? <Pause size={15} /> : <Play size={15} />}
        </button>
        <button aria-label="下一帧" onClick={() => onSelect(Math.min(steps.length - 1, selectedIndex + 1))}><SkipForward size={14} /></button>
        <span className="step-count">STEP <b>{selected?.index ?? 0}</b> / {Math.max(0, steps.length - 1)}</span>
        <select value={speed} onChange={(event) => onSpeed(Number(event.target.value))} aria-label="回放速度">
          <option value={0.5}>0.5×</option>
          <option value={1}>1×</option>
          <option value={2}>2×</option>
          <option value={4}>4×</option>
        </select>
      </div>
      <div className="timeline-track" aria-label="动作时间线">
        {steps.map((step, index) => (
          <button
            key={`${step.index}-${step.timestamp}`}
            className={`tick ${index === selectedIndex ? 'active' : ''} ${step.levels_completed > (steps[index - 1]?.levels_completed ?? 0) ? 'level-up' : ''}`}
            style={{ left: `${steps.length <= 1 ? 0 : (index / (steps.length - 1)) * 100}%` }}
            onClick={() => onSelect(index)}
            aria-label={`第 ${step.index} 步 ${step.action_name}`}
            title={`${step.index} · ${step.action_name}`}
          />
        ))}
        <div className="timeline-fill" style={{ width: `${steps.length <= 1 ? 0 : (selectedIndex / (steps.length - 1)) * 100}%` }} />
      </div>
      <div className="timeline-caption">
        <span>{selected?.action_name ?? '等待首帧'}</span>
        <span>{selected ? `${selected.changed_cells} cells Δ · ${selected.duration_ms} ms` : '—'}</span>
      </div>
    </section>
  )
}

