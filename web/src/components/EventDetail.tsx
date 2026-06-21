import { Binary, Braces, BrainCircuit, Columns2, Database, ListTree, MousePointerClick, ScanSearch } from 'lucide-react'
import type { ReactNode } from 'react'
import type { TraceStep } from '../types'
import { PixelGrid } from './PixelGrid'

export type DetailTab = 'trajectory' | 'input' | 'perception' | 'decision' | 'operation' | 'diff' | 'raw'

interface EventDetailProps {
  steps: TraceStep[]
  selectedIndex: number
  tab: DetailTab
  onTab: (tab: DetailTab) => void
  onSelect: (index: number) => void
}

function DataSection({ title, meta, children }: { title: string; meta?: string; children: ReactNode }) {
  return (
    <section className="data-section">
      <div className="data-section-head"><strong>{title}</strong>{meta && <span>{meta}</span>}</div>
      <div className="data-section-body">{children}</div>
    </section>
  )
}

function JsonPanel({ value }: { value: unknown }) {
  return <pre className="json-panel">{JSON.stringify(value, null, 2)}</pre>
}

export function EventDetail({ steps, selectedIndex, tab, onTab, onSelect }: EventDetailProps) {
  const selected = steps[selectedIndex]
  const stats = selected ? Object.entries(selected.agent_state_before?.action_stats ?? {}) : []
  return (
    <section className="event-detail">
      <div className="detail-tabs">
        <button className={tab === 'trajectory' ? 'active' : ''} onClick={() => onTab('trajectory')}><ListTree size={13} />轨迹</button>
        <button className={tab === 'input' ? 'active' : ''} onClick={() => onTab('input')}><Database size={13} />完整输入</button>
        <button className={tab === 'perception' ? 'active' : ''} onClick={() => onTab('perception')}><ScanSearch size={13} />对象解析</button>
        <button className={tab === 'decision' ? 'active' : ''} onClick={() => onTab('decision')}><BrainCircuit size={13} />决策状态</button>
        <button className={tab === 'operation' ? 'active' : ''} onClick={() => onTab('operation')}><MousePointerClick size={13} />实际操作</button>
        <button className={tab === 'diff' ? 'active' : ''} onClick={() => onTab('diff')}><Columns2 size={13} />帧差异</button>
        <button className={tab === 'raw' ? 'active' : ''} onClick={() => onTab('raw')}><Braces size={13} />完整事件</button>
        <span>{steps.length} EVENTS</span>
      </div>
      <div className="detail-content">
        {tab === 'trajectory' && (
          <div className="event-table">
            <div className="event-row event-head"><span>#</span><span>动作</span><span>结果</span><span>Δ</span><span>延迟</span></div>
            {steps.slice().reverse().map((step) => (
              <button className={`event-row ${step.index === selectedIndex ? 'selected' : ''}`} key={step.index} onClick={() => onSelect(step.index)}>
                <span>{String(step.index).padStart(2, '0')}</span>
                <b>{step.action_name}</b>
                <span>{step.state} · {step.levels_completed}/{step.win_levels}</span>
                <span>{step.changed_cells}</span>
                <span>{step.duration_ms} ms</span>
              </button>
            ))}
          </div>
        )}

        {tab === 'input' && selected && (
          <div className="data-grid input-grid">
            <DataSection title="环境元数据" meta="AGENT RECEIVES">
              <JsonPanel value={selected.observation_input} />
            </DataSection>
            <DataSection title="原始帧图层" meta={`${selected.raw_frame_layers.length} LAYERS`}>
              <div className="layer-strip">
                {selected.raw_frame_layers.map((layer, index) => (
                  <div className="layer-item" key={index}><span>LAYER {index}</span><PixelGrid frame={layer} label={`原始图层 ${index}`} /></div>
                ))}
              </div>
            </DataSection>
            <DataSection title="完整动作空间" meta={`${selected.available_action_details.length} ACTIONS`}>
              <div className="compact-table action-space-table">
                <div className="compact-head"><span>ID</span><span>NAME</span><span>TYPE</span><span>DATA SCHEMA</span></div>
                {selected.available_action_details.map((action) => (
                  <div className="compact-row" key={action.id}>
                    <span>{action.id}</span><b>{action.name}</b><span>{action.is_complex ? 'x, y' : 'simple'}</span><code>{JSON.stringify(action.data_schema)}</code>
                  </div>
                ))}
              </div>
            </DataSection>
          </div>
        )}

        {tab === 'perception' && selected && (
          <div className="data-grid perception-grid">
            <DataSection title="颜色直方图" meta={`BACKGROUND ${selected.perception.background_color}`}>
              <div className="histogram-list">
                {selected.perception.color_histogram.map((entry) => (
                  <div key={entry.color}><span className={`color-swatch color-${entry.color % 16}`} /><b>{entry.color}</b><i style={{ width: `${Math.max(2, entry.count / (selected.perception.width * selected.perception.height) * 100)}%` }} /><em>{entry.count}</em></div>
                ))}
              </div>
            </DataSection>
            <DataSection title="连通区域 / 对象" meta={`${selected.perception.components.length} COMPONENTS`}>
              <div className="compact-table object-table">
                <div className="compact-head"><span>#</span><span>COLOR</span><span>SIZE</span><span>CENTER</span><span>BOUNDS</span></div>
                {selected.perception.components.map((component) => (
                  <div className="compact-row" key={component.id}>
                    <span>{component.id}</span>
                    <span><i className={`color-swatch color-${component.color % 16}`} />{component.color}</span>
                    <b>{component.size}</b>
                    <code>{component.center.x}, {component.center.y}</code>
                    <code>{component.bounds.x_min},{component.bounds.y_min} → {component.bounds.x_max},{component.bounds.y_max}</code>
                  </div>
                ))}
              </div>
            </DataSection>
          </div>
        )}

        {tab === 'decision' && selected && (
          <div className="data-grid decision-grid">
            <DataSection title="Agent 内部状态" meta={`BEFORE STEP ${selected.index}`}>
              <div className="policy-line"><Binary size={13} /><span>{selected.agent_state_before.policy}</span></div>
              <div className="compact-table stats-table">
                <div className="compact-head"><span>ACTION</span><span>TRIALS</span><span>TOTAL REWARD</span><span>MEAN</span></div>
                {stats.length ? stats.map(([name, value]) => (
                  <div className="compact-row" key={name}><b>{name}</b><span>{value.trials}</span><span>{value.cumulative_information_reward}</span><span>{value.mean_information_reward}</span></div>
                )) : <div className="empty-row">尚无动作历史</div>}
              </div>
            </DataSection>
            <DataSection title="本步全部候选" meta={`${selected.candidates.length} CANDIDATES`}>
              <div className="compact-table candidate-table">
                <div className="compact-head"><span>RANK</span><span>ACTION</span><span>DATA</span><span>SCORE</span><span>EVIDENCE</span></div>
                {selected.candidates.length ? selected.candidates.map((candidate, index) => (
                  <div className={`compact-row ${index === 0 ? 'chosen-row' : ''}`} key={`${candidate.action}-${index}`}>
                    <span>{index + 1}</span><b>{candidate.action}</b><code>{JSON.stringify(candidate.data)}</code><strong>{candidate.score.toFixed(3)}</strong><span>{candidate.evidence}</span>
                  </div>
                )) : <div className="empty-row">RESET 没有候选动作</div>}
              </div>
            </DataSection>
            <DataSection title="点击探索队列" meta={`${selected.agent_state_before.pending_click_candidates.length} PENDING`}>
              <JsonPanel value={{ pending: selected.agent_state_before.pending_click_candidates, used: selected.agent_state_before.used_clicks }} />
            </DataSection>
          </div>
        )}

        {tab === 'operation' && selected && (
          <div className="operation-grid">
            <DataSection title="Agent 发出的实际请求" meta="REQUEST"><JsonPanel value={selected.action_request} /></DataSection>
            <DataSection title="官方环境返回" meta="RESPONSE"><JsonPanel value={selected.environment_response} /></DataSection>
          </div>
        )}

        {tab === 'diff' && selected && (
          <div className="diff-layout">
            <div className="diff-view">
              <div><span>BEFORE</span><PixelGrid frame={selected.before_frame ?? selected.frame} label="动作前帧" /></div>
              <div className="diff-summary"><strong>{selected.changed_cells}</strong><span>changed cells</span><p>{selected.detected_change}</p></div>
              <div><span>AFTER</span><PixelGrid frame={selected.frame} beforeFrame={selected.before_frame} showDiff label="动作后帧" /></div>
            </div>
            <DataSection title="全部变化像素" meta={`${selected.changed_pixels.length} ROWS`}>
              <div className="pixel-change-list">
                {selected.changed_pixels.map((pixel, index) => <code key={`${pixel.x}-${pixel.y}-${index}`}>({pixel.x},{pixel.y}) {pixel.before}→{pixel.after}</code>)}
              </div>
            </DataSection>
          </div>
        )}

        {tab === 'raw' && selected && <pre className="raw-event">{JSON.stringify(selected, null, 2)}</pre>}
      </div>
    </section>
  )
}
