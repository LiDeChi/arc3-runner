import { Activity, BrainCircuit, Eye, GitBranch, ListTree, MousePointerClick, ScanSearch } from 'lucide-react'
import type { TraceStep } from '../types'
import type { InterfaceMode } from '../types'
import { PixelGrid } from './PixelGrid'
import { CompactJson } from './CompactJson'

interface VisualGameInterfaceProps {
  step?: TraceStep
  gameId: string
  mode: InterfaceMode
  onModeChange: (mode: InterfaceMode) => void
}

export function VisualGameInterface({ step, gameId, mode, onModeChange }: VisualGameInterfaceProps) {
  if (!step) {
    return (
      <div className="vgi-empty">
        <Activity size={22} />
        <span>等待环境首帧</span>
      </div>
    )
  }

  return (
    <div className="vgi">
      <div className="vgi-header">
        <div className="vgi-mode-switch">
          <button className={`vgi-mode-btn ${mode === 'visual' ? 'active' : ''}`} onClick={() => onModeChange('visual')}>
            <Eye size={13} /> 可视化
          </button>
          <button className={`vgi-mode-btn ${mode === 'data' ? 'active' : ''}`} onClick={() => onModeChange('data')}>
            <ListTree size={13} /> 数据
          </button>
        </div>
        <div className="vgi-header-info">
          <span className="vgi-step-label">{gameId}</span>
          <span className="vgi-step-num">STEP {String(step.index).padStart(3, '0')}</span>
          <span className="vgi-action-badge">{step.action_name}</span>
          <span className="vgi-level-badge">L{step.levels_completed}/{step.win_levels || '—'}</span>
          {step.changed_cells > 0 && <span className="vgi-change-badge">{step.changed_cells} Δ</span>}
          <span className="vgi-duration">{step.duration_ms}ms</span>
        </div>
      </div>

      {mode === 'visual' ? (
        <div className="vgi-visual">
          <div className="vgi-frame-section">
            <PixelGrid
              frame={step.frame}
              beforeFrame={step.before_frame}
              showDiff={false}
              label={`${gameId} 第 ${step.index} 帧`}
            />
            <div className="vgi-frame-meta">
              <span>64 × 64</span>
              <span>{step.perception.color_histogram.length} colors</span>
              <span>{step.perception.components.length} components</span>
            </div>
          </div>

          <div className="vgi-sidebar">
            <div className="vgi-panel vgi-observation">
              <div className="vgi-panel-head">
                <Eye size={12} />
                <span>观察</span>
              </div>
              <p>{step.observation}</p>
            </div>

            <div className="vgi-panel vgi-change">
              <div className="vgi-panel-head">
                <ScanSearch size={12} />
                <span>帧变化</span>
              </div>
              <p>{step.detected_change}</p>
            </div>

            <div className="vgi-panel vgi-hypothesis">
              <div className="vgi-panel-head">
                <GitBranch size={12} />
                <span>假设</span>
              </div>
              <p>{step.hypothesis}</p>
            </div>

            <div className="vgi-panel vgi-action-space">
              <div className="vgi-panel-head">
                <MousePointerClick size={12} />
                <span>动作空间 ({step.available_action_details.length})</span>
              </div>
              <div className="vgi-action-grid">
                {step.available_action_details.map((action) => (
                  <div className={`vgi-action-chip ${action.id === step.action_id ? 'used' : ''}`} key={action.id}>
                    <b>{action.id}</b>
                    <span>{action.name}</span>
                    <span className="vgi-action-type">{action.is_complex ? 'x,y' : 'simple'}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="vgi-panel vgi-candidates">
              <div className="vgi-panel-head">
                <BrainCircuit size={12} />
                <span>候选动作 ({step.candidates.length})</span>
              </div>
              <div className="vgi-candidate-list">
                {step.candidates.length === 0 && <p className="vgi-no-data">无候选</p>}
                {step.candidates.slice(0, 5).map((candidate, index) => (
                  <div className={`vgi-candidate ${index === 0 ? 'chosen' : ''}`} key={`${candidate.action}-${index}`}>
                    <span className="vgi-cand-rank">{String(index + 1).padStart(2, '0')}</span>
                    <span className="vgi-cand-name">{candidate.action}</span>
                    <span className="vgi-cand-bar">
                      <i style={{ width: `${Math.min(100, candidate.score * 18)}%` }} />
                    </span>
                    <span className="vgi-cand-score">{candidate.score.toFixed(3)}</span>
                    <span className="vgi-cand-evi">{candidate.evidence}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="vgi-panel vgi-result accent">
              <div className="vgi-panel-head">
                <MousePointerClick size={12} />
                <span>执行动作</span>
              </div>
              <div className="vgi-exec-row">
                <strong>{step.action_name}</strong>
                {Object.keys(step.action_data).length > 0 && (
                  <code>{JSON.stringify(step.action_data)}</code>
                )}
              </div>
              <p className="vgi-reason">{step.selected_reason}</p>
              <p className="vgi-result-text">{step.result}</p>
            </div>
          </div>
        </div>
      ) : (
        <div className="vgi-data">
          <div className="vgi-data-grid">
            <DataBlock title="Obseration Input" data={step.observation_input} />
            <DataBlock title="Action Request" data={step.action_request} />
            <DataBlock title="Environment Response" data={step.environment_response} />
            <DataBlock title="Agent State Before" data={step.agent_state_before} />
            <DataBlock title="Raw Frame Layers" data={{ layer_count: step.raw_frame_layers.length, shapes: step.raw_frame_layers.map((l, i) => `layer${i}: ${l.length}×${l[0]?.length || 0}`) }} />
            <DataBlock title="Perception" data={step.perception} />
          </div>
        </div>
      )}
    </div>
  )
}

function DataBlock({ title, data }: { title: string; data: unknown }) {
  return (
    <div className="vgi-data-block">
      <div className="vgi-data-block-head">{title}</div>
      <div className="vgi-data-block-body">
        <CompactJson data={data} expandDepth={3} />
      </div>
    </div>
  )
}
