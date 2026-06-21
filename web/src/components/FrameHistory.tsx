import { useRef } from 'react'
import { Columns, List, Pause, Play, RotateCcw, SkipBack, SkipForward, LayoutGrid, StepForward } from 'lucide-react'
import type { TraceStep, HistoryViewMode } from '../types'
import { PixelGrid } from './PixelGrid'

interface FrameHistoryProps {
  steps: TraceStep[]
  selectedIndex: number
  playing: boolean
  speed: number
  viewMode: HistoryViewMode
  onPlaying: (value: boolean) => void
  onSelect: (index: number) => void
  onSpeed: (speed: number) => void
  onViewMode: (mode: HistoryViewMode) => void
}

export function FrameHistory({ steps, selectedIndex, playing, speed, viewMode, onPlaying, onSelect, onSpeed, onViewMode }: FrameHistoryProps) {
  const selected = steps[selectedIndex]
  const galleryRef = useRef<HTMLDivElement>(null)

  if (steps.length === 0) {
    return (
      <section className="fh">
        <div className="fh-empty">等待帧数据…</div>
      </section>
    )
  }

  const scrollToIndex = (index: number) => {
    if (viewMode !== 'gallery' || !galleryRef.current) return
    const card = galleryRef.current.children[index] as HTMLElement
    if (card) card.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' })
  }

  const handleSelect = (index: number) => {
    onSelect(index)
    scrollToIndex(index)
  }

  return (
    <section className="fh">
      <div className="fh-top">
        <div className="transport">
          <button aria-label="回到首帧" onClick={() => handleSelect(0)}><RotateCcw size={13} /></button>
          <button aria-label="上一帧" onClick={() => handleSelect(Math.max(0, selectedIndex - 1))}><SkipBack size={13} /></button>
          <button className="play-button" aria-label={playing ? '暂停' : '播放'} onClick={() => onPlaying(!playing)}>
            {playing ? <Pause size={14} /> : <Play size={14} />}
          </button>
          <button aria-label="下一帧" onClick={() => handleSelect(Math.min(steps.length - 1, selectedIndex + 1))}><SkipForward size={13} /></button>
          <button aria-label="重新回放" onClick={() => { onSelect(0); onPlaying(true) }}><StepForward size={13} /></button>
          <span className="step-count">STEP <b>{selected?.index ?? 0}</b> / {Math.max(0, steps.length - 1)}</span>
          <select value={speed} onChange={(event) => onSpeed(Number(event.target.value))} aria-label="回放速度">
            <option value={0.5}>0.5×</option>
            <option value={1}>1×</option>
            <option value={2}>2×</option>
            <option value={4}>4×</option>
          </select>
        </div>
        <div className="fh-view-controls">
          <span className="section-label">VIEW</span>
          <button className={`fh-view-btn ${viewMode === 'gallery' ? 'active' : ''}`} onClick={() => onViewMode('gallery')} title="画廊">
            <LayoutGrid size={13} />
          </button>
          <button className={`fh-view-btn ${viewMode === 'list' ? 'active' : ''}`} onClick={() => onViewMode('list')} title="列表">
            <List size={13} />
          </button>
          <button className={`fh-view-btn ${viewMode === 'timeline' ? 'active' : ''}`} onClick={() => onViewMode('timeline')} title="时间线">
            <Columns size={13} />
          </button>
        </div>
      </div>

      <div className="fh-body">
        {/* Gallery view */}
        {viewMode === 'gallery' && (
          <div className="fh-gallery" ref={galleryRef}>
            {steps.map((step, index) => (
              <div
                key={step.index}
                className={`fh-card ${index === selectedIndex ? 'selected' : ''} ${step.levels_completed > (steps[index - 1]?.levels_completed ?? 0) ? 'level-up' : ''}`}
                onClick={() => handleSelect(index)}
                role="button"
                tabIndex={0}
              >
                <div className="fh-card-frame">
                  <PixelGrid frame={step.frame} label={`帧 ${step.index}`} />
                </div>
                <div className="fh-card-info">
                  <span className="fh-card-step">{String(step.index).padStart(2, '0')}</span>
                  <b className="fh-card-action">{step.action_name}</b>
                  <span className="fh-card-state">{step.state}</span>
                  <span className="fh-card-level">L{step.levels_completed}/{step.win_levels || '—'}</span>
                  {step.changed_cells > 0 && <span className="fh-card-delta">{step.changed_cells}Δ</span>}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* List view */}
        {viewMode === 'list' && (
          <div className="fh-list">
            <div className="fh-list-head">
              <span>#</span><span>Action</span><span>State</span><span>Level</span><span>Δ cells</span><span>Time</span><span>Duration</span>
            </div>
            {steps.map((step, index) => (
              <div
                className={`fh-list-row ${index === selectedIndex ? 'selected' : ''}`}
                key={step.index}
                onClick={() => handleSelect(index)}
                role="button"
                tabIndex={0}
              >
                <span>{String(step.index).padStart(2, '0')}</span>
                <b>{step.action_name}</b>
                <span className="fh-list-state">{step.state}</span>
                <span>{step.levels_completed}/{step.win_levels || '—'}</span>
                <span>{step.changed_cells}</span>
                <span className="fh-list-time">{new Date(step.timestamp).toLocaleTimeString()}</span>
                <span className="fh-list-duration">{step.duration_ms}ms</span>
              </div>
            ))}
          </div>
        )}

        {/* Timeline view */}
        {viewMode === 'timeline' && (
          <div className="fh-timeline-view">
            <div className="fh-timeline-track">
              {steps.map((step, index) => (
                <button
                  key={step.index}
                  className={`fh-tick ${index === selectedIndex ? 'active' : ''} ${step.levels_completed > (steps[index - 1]?.levels_completed ?? 0) ? 'level-up' : ''}`}
                  style={{ left: `${steps.length <= 1 ? 5 : (index / (steps.length - 1)) * 95 + 2.5}%` }}
                  onClick={() => handleSelect(index)}
                  title={`${step.index} · ${step.action_name}`}
                />
              ))}
              <div className="fh-timeline-fill" style={{ width: `${steps.length <= 1 ? 0 : (selectedIndex / (steps.length - 1)) * 100}%` }} />
            </div>
            <div className="fh-detail-bar">
              <div className="fh-detail-left">
                <span className="fh-detail-action"><b>{selected?.action_name}</b></span>
                <span className="fh-detail-reason">{selected?.selected_reason}</span>
              </div>
              <div className="fh-detail-right">
                <span className="fh-detail-result">{selected?.result}</span>
              </div>
            </div>
          </div>
        )}
      </div>
    </section>
  )
}
