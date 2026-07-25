import { Pause, Play, RotateCcw, SkipBack, SkipForward, LayoutGrid, List, GitBranch } from 'lucide-react'
import { useRef } from 'react'
import type { HistoryViewMode, TraceStep } from '../types'
import { PixelGrid } from './PixelGrid'

interface FrameHistoryProps {
  steps: TraceStep[]
  selectedIndex: number
  playing: boolean
  speed: number
  viewMode: HistoryViewMode
  onViewMode: (mode: HistoryViewMode) => void
  onPlaying: (value: boolean) => void
  onSelect: (index: number) => void
  onSpeed: (speed: number) => void
  onRerun: () => void
  canRerun: boolean
}

function surpriseValue(step: TraceStep): number {
  return Math.max(0, Math.min(1, step.surprise?.value ?? 0))
}

function surpriseStyle(step: TraceStep): { backgroundColor: string } {
  const value = surpriseValue(step)
  if (value <= 0) return { backgroundColor: '#5e666f' }
  return { backgroundColor: `rgba(239, 51, 64, ${0.25 + value * 0.75})` }
}

export function FrameHistory({
  steps,
  selectedIndex,
  playing,
  speed,
  viewMode,
  onViewMode,
  onPlaying,
  onSelect,
  onSpeed,
  onRerun,
  canRerun,
}: FrameHistoryProps) {
  const safeIndex = Math.min(selectedIndex, Math.max(0, steps.length - 1))
  const selected = steps[safeIndex]

  return (
    <section className="frame-history">
      {/* Transport */}
      <div className="transport">
        <div className="transport-left">
          <button aria-label="回到首帧" onClick={() => onSelect(0)}><RotateCcw size={14} /></button>
          <button aria-label="上一帧" onClick={() => onSelect(Math.max(0, safeIndex - 1))}><SkipBack size={14} /></button>
          <button className="play-button" aria-label={playing ? '暂停' : '播放'} onClick={() => onPlaying(!playing)}>
            {playing ? <Pause size={15} /> : <Play size={15} />}
          </button>
          <button aria-label="下一帧" onClick={() => onSelect(Math.min(steps.length - 1, safeIndex + 1))}><SkipForward size={14} /></button>
          <span className="step-count">STEP <b>{selected?.index ?? 0}</b> / {Math.max(0, steps.length - 1)}</span>
          <select value={speed} onChange={(event) => onSpeed(Number(event.target.value))} aria-label="回放速度">
            <option value={0.5}>0.5×</option>
            <option value={1}>1×</option>
            <option value={2}>2×</option>
            <option value={4}>4×</option>
          </select>
        </div>
        <div className="transport-right">
          <div className="view-toggle">
            <button
              className={`view-btn ${viewMode === 'gallery' ? 'active' : ''}`}
              onClick={() => onViewMode('gallery')}
              aria-label="画廊视图"
              title="画廊"
            >
              <LayoutGrid size={14} />
            </button>
            <button
              className={`view-btn ${viewMode === 'list' ? 'active' : ''}`}
              onClick={() => onViewMode('list')}
              aria-label="列表视图"
              title="列表"
            >
              <List size={14} />
            </button>
            <button
              className={`view-btn ${viewMode === 'timeline' ? 'active' : ''}`}
              onClick={() => onViewMode('timeline')}
              aria-label="时间线视图"
              title="时间线"
            >
              <GitBranch size={14} />
            </button>
          </div>
          <button className="rerun-btn" onClick={onRerun} disabled={!canRerun} title="以当前策略重玩本环境">
            <RotateCcw size={13} /> 重玩
          </button>
        </div>
      </div>

      {/* View content */}
      <div className="fh-content">
        {viewMode === 'gallery' && (
          <GalleryView steps={steps} selectedIndex={safeIndex} onSelect={onSelect} />
        )}
        {viewMode === 'list' && (
          <ListView steps={steps} selectedIndex={safeIndex} onSelect={onSelect} />
        )}
        {viewMode === 'timeline' && (
          <TimelineView steps={steps} selectedIndex={safeIndex} onSelect={onSelect} />
        )}
      </div>

      {/* Caption */}
      {selected && (
        <div className="fh-caption">
          <span className="fh-action">{selected.action_name}</span>
          <span className="fh-meta">{selected.state} · {selected.levels_completed}/{selected.win_levels} · {selected.changed_cells} cells Δ · {selected.duration_ms} ms</span>
        </div>
      )}
    </section>
  )
}

function GalleryView({ steps, selectedIndex, onSelect }: { steps: TraceStep[]; selectedIndex: number; onSelect: (i: number) => void }) {
  const scrollRef = useRef<HTMLDivElement>(null)

  return (
    <div className="fh-gallery" ref={scrollRef}>
      {steps.map((step, index) => (
        <button
          className={`fh-card ${index === selectedIndex ? 'selected' : ''} ${step.levels_completed > (steps[index - 1]?.levels_completed ?? 0) ? 'level-up' : ''}`}
          key={`${step.index}-${step.timestamp}`}
          onClick={() => onSelect(index)}
        >
          <div className="fh-card-frame">
            <PixelGrid frame={step.frame} label={`第 ${step.index} 帧`} />
          </div>
          <div className="fh-card-info">
            <span className="fh-card-step">#{String(step.index).padStart(2, '0')}</span>
            <span className="fh-card-action">{step.action_name}</span>
          </div>
          <div className="fh-card-meta">
            <span>{step.levels_completed}/{step.win_levels}</span>
            <span>{step.changed_cells}Δ</span>
            <span className={`surprise-pill ${surpriseValue(step) >= 0.3 ? 'hot' : ''}`}>S {surpriseValue(step).toFixed(2)}</span>
          </div>
        </button>
      ))}
    </div>
  )
}

function ListView({ steps, selectedIndex, onSelect }: { steps: TraceStep[]; selectedIndex: number; onSelect: (i: number) => void }) {
  return (
    <div className="fh-list">
      <div className="event-table">
        <div className="event-row event-head"><span>#</span><span>动作</span><span>结果</span><span>Δ</span><span>惊奇</span><span>延迟</span></div>
        {steps.slice().reverse().map((step) => (
          <button
            className={`event-row ${step.index === selectedIndex ? 'selected' : ''}`}
            key={step.index}
            onClick={() => onSelect(step.index)}
          >
            <span>{String(step.index).padStart(2, '0')}</span>
            <b>{step.action_name}</b>
            <span>{step.state} · {step.levels_completed}/{step.win_levels}</span>
            <span>{step.changed_cells}</span>
            <span className={surpriseValue(step) >= 0.3 ? 'surprise-hot-text' : ''}>{surpriseValue(step).toFixed(2)}</span>
            <span>{step.duration_ms} ms</span>
          </button>
        ))}
      </div>
    </div>
  )
}

function TimelineView({ steps, selectedIndex, onSelect }: { steps: TraceStep[]; selectedIndex: number; onSelect: (i: number) => void }) {
  return (
    <div className="fh-timeline">
      <div className="timeline-track" aria-label="动作时间线">
        {steps.map((step, index) => (
          <button
            key={`${step.index}-${step.timestamp}`}
            className={`tick ${index === selectedIndex ? 'active' : ''} ${step.levels_completed > (steps[index - 1]?.levels_completed ?? 0) ? 'level-up' : ''} ${step.surprise?.belief_flips?.length ? 'belief-flip' : ''}`}
            style={{ left: `${steps.length <= 1 ? 0 : (index / (steps.length - 1)) * 100}%`, ...surpriseStyle(step) }}
            onClick={() => onSelect(index)}
            aria-label={`第 ${step.index} 步 ${step.action_name}`}
            title={`${step.index} · ${step.action_name} · surprise ${surpriseValue(step).toFixed(2)}`}
          >
            {step.surprise?.belief_flips?.length ? <span className="belief-flip-mark">⚡</span> : null}
          </button>
        ))}
        <div className="timeline-fill" style={{ width: `${steps.length <= 1 ? 0 : (selectedIndex / (steps.length - 1)) * 100}%` }} />
      </div>
    </div>
  )
}
