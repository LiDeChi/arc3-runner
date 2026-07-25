import { Binary, Braces, BrainCircuit, Circle, Columns2, Eye, Image, ListTree, MousePointer2, ScanSearch, Sparkles } from 'lucide-react'
import { useState } from 'react'
import type { InterfaceMode, TraceStep } from '../types'
import { PixelGrid } from './PixelGrid'
import { CompactJson } from './CompactJson'
import { DecisionCard } from './DecisionCard'
import { ImaginationView } from './ImaginationView'

interface VisualGameInterfaceProps {
  step: TraceStep | undefined
  stepIndex: number
  totalSteps: number
  gameId: string
  levelsCompleted: number
  winLevels: number | null
  actionCount: number
  stateLabel: string
  gameStatus: string
  interfaceMode: InterfaceMode
  onMode: (mode: InterfaceMode) => void
}

function StatusBadge({ label, running }: { label: string; running: boolean }) {
  return (
    <div className={`vgi-badge ${running ? 'is-running' : ''}`}>
      <Circle size={6} fill="currentColor" />
      <span>{label}</span>
    </div>
  )
}

export function VisualGameInterface({
  step,
  stepIndex,
  totalSteps,
  gameId,
  levelsCompleted,
  winLevels,
  actionCount,
  stateLabel,
  gameStatus,
  interfaceMode,
  onMode,
  showDiff = false,
  onDiffToggle,
}: VisualGameInterfaceProps & { showDiff?: boolean; onDiffToggle?: () => void }) {
  const progress = winLevels ? Math.round((levelsCompleted / winLevels) * 100) : 0
  const isRunning = gameStatus === 'running'

  return (
    <section className="vgi">
      {/* Header */}
      <div className="vgi-header">
        <div className="vgi-title">
          <StatusBadge label={stateLabel} running={isRunning} />
          <div>
            <span className="section-label">GAME DETAIL</span>
            <h1>{gameId}</h1>
          </div>
        </div>
        <div className="vgi-stats">
          <div><span>LEVEL</span><b>{levelsCompleted}<i>/ {winLevels ?? '—'}</i></b></div>
          <div><span>ACTIONS</span><b>{actionCount}</b></div>
          <div><span>PROGRESS</span><b>{progress}%</b></div>
          <div><span>STEP</span><b>{stepIndex}<i>/ {totalSteps}</i></b></div>
        </div>
        <div className="vgi-mode-toggle">
          <button
            className={`vgi-mode-btn ${interfaceMode === 'visual' ? 'active' : ''}`}
            onClick={() => onMode('visual')}
            title="可视化游戏界面"
          >
            <Image size={13} /> 界面
          </button>
          <button
            className={`vgi-mode-btn ${interfaceMode === 'data' ? 'active' : ''}`}
            onClick={() => onMode('data')}
            title="等价数据界面"
          >
            <Braces size={13} /> 数据
          </button>
          {onDiffToggle && (
            <button
              className={`vgi-mode-btn ${showDiff ? '' : ''}`}
              onClick={onDiffToggle}
              title="切换帧差异高亮"
              style={{ opacity: showDiff ? 1 : 0.5 }}
            >
              <Columns2 size={13} /> 差异
            </button>
          )}
        </div>
      </div>

      {/* Body */}
      <div className="vgi-body">
        {interfaceMode === 'visual' ? (
          <VisualView step={step} showDiff={showDiff} />
        ) : (
          <DataView step={step} />
        )}
      </div>
    </section>
  )
}

function VisualView({ step, showDiff = false }: { step: TraceStep | undefined; showDiff?: boolean }) {
  const [showImagination, setShowImagination] = useState(false)

  if (!step) {
    return (
      <div className="vgi-visual-layout">
        <div className="vgi-frame-area">
          <div className="frame-loading"><Eye size={22} /><span>等待首帧</span></div>
        </div>
      </div>
    )
  }

  const hasImagination = Boolean(step.imagination?.predicted_frame)
  const surpriseHot = (step.surprise?.value ?? 0) >= 0.3

  return (
    <div className="vgi-visual-layout">
      {/* Left: frame */}
      <div className="vgi-frame-area">
        <button
          className={`imagination-toggle ${showImagination ? 'active' : ''} ${surpriseHot ? 'hot' : ''}`}
          onClick={() => setShowImagination((value) => !value)}
          disabled={!hasImagination}
          title={hasImagination ? '想象对比：动作前 / 预测 / 实际' : '本步没有预测帧'}
          aria-label="切换想象对比"
        >
          <Sparkles size={13} />
          {surpriseHot && <i />}
        </button>
        {showImagination && hasImagination ? (
          <ImaginationView step={step} />
        ) : (
          <>
            <div className="vgi-frame-corners" aria-hidden="true" />
            <PixelGrid
              frame={step.frame}
              beforeFrame={step.before_frame}
              showDiff={showDiff}
              label={`第 ${step.index} 帧`}
            />
          </>
        )}
        <div className="vgi-frame-labels">
          <span>64 × 64 OBSERVATION</span>
          <span>FRAME {String(step.index).padStart(3, '0')}</span>
        </div>
      </div>

      {/* Right: info panels */}
      <div className="vgi-sidebar">
        <DecisionCard step={step} />

        {/* Current action */}
        <div className="vgi-panel vgi-action">
          <div className="vgi-panel-head"><MousePointer2 size={12} />执行动作</div>
          <div className="vgi-panel-body">
            <div className="vgi-action-row">
              <strong className="vgi-action-name">{step.action_name}</strong>
              {Object.keys(step.action_data).length > 0 && (
                <code className="vgi-action-data">{JSON.stringify(step.action_data)}</code>
              )}
            </div>
            {step.index > 0 && <p className="vgi-reason">{step.selected_reason}</p>}
          </div>
        </div>

        {/* Candidates */}
        <div className="vgi-panel vgi-candidates">
          <div className="vgi-panel-head"><BrainCircuit size={12} />候选动作 · {step.candidates.length}</div>
          <div className="vgi-panel-body vgi-candidate-list">
            {step.candidates.length > 0 ? (
              step.candidates.slice(0, 5).map((candidate, idx) => (
                <div className={`vgi-candidate ${idx === 0 ? 'chosen' : ''}`} key={`${candidate.action}-${idx}`}>
                  <span className="vgi-cand-rank">{idx + 1}</span>
                  <b className="vgi-cand-name">{candidate.action}</b>
                  <i className="vgi-cand-bar" style={{ width: `${Math.min(100, candidate.score * 20)}%` }} />
                  <em className="vgi-cand-score">{candidate.score.toFixed(3)}</em>
                  <span className="vgi-cand-evidence">{candidate.evidence}</span>
                </div>
              ))
            ) : (
              <span className="vgi-empty">RESET — 无候选动作</span>
            )}
          </div>
        </div>

        {/* Observation / change summary */}
        <div className="vgi-panel vgi-observation">
          <div className="vgi-panel-head"><ScanSearch size={12} />观察</div>
          <div className="vgi-panel-body">
            <p>{step.observation}</p>
            <div className="vgi-metric-line">
              <span>变化</span><b>{step.changed_cells} cells</b>
            </div>
            <p className="vgi-change">{step.detected_change}</p>
            {step.hypothesis && <p className="vgi-hypothesis">{step.hypothesis}</p>}
          </div>
        </div>

        {/* Result */}
        <div className="vgi-panel vgi-result">
          <div className="vgi-panel-head"><ListTree size={12} />结果</div>
          <div className="vgi-panel-body">
            <span>{step.result}</span>
            <span className="vgi-latency">{step.duration_ms} ms</span>
          </div>
        </div>
      </div>
    </div>
  )
}

function DataView({ step }: { step: TraceStep | undefined }) {
  if (!step) {
    return <div className="vgi-data-layout"><span className="vgi-empty">选择一步以查看数据</span></div>
  }

  return (
    <div className="vgi-data-layout">
      {/* Action space */}
      <div className="data-section">
        <div className="data-section-head"><strong>完整动作空间</strong><span>{step.available_action_details.length} ACTIONS</span></div>
        <div className="data-section-body">
          <div className="compact-table action-space-table">
            <div className="compact-head"><span>ID</span><span>NAME</span><span>TYPE</span><span>DATA SCHEMA</span></div>
            {step.available_action_details.map((action) => (
              <div className="compact-row" key={action.id}>
                <span>{action.id}</span>
                <b>{action.name}</b>
                <span>{action.is_complex ? 'x, y' : 'simple'}</span>
                <CompactJson value={action.data_schema} defaultExpand={0} />
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Observation input */}
      <div className="data-section">
        <div className="data-section-head"><strong>环境元数据 / 观察输入</strong><span>AGENT RECEIVES</span></div>
        <div className="data-section-body data-json-body">
          <CompactJson value={step.observation_input} />
        </div>
      </div>

      {/* Agent state */}
      <div className="data-section">
        <div className="data-section-head"><strong>Agent 内部状态</strong><span>BEFORE STEP {step.index}</span></div>
        <div className="data-section-body">
          <div className="policy-line"><Binary size={13} /><span>{step.agent_state_before.policy}</span></div>
          <div className="compact-table stats-table">
            <div className="compact-head"><span>ACTION</span><span>TRIALS</span><span>TOTAL REWARD</span><span>MEAN</span></div>
            {Object.entries(step.agent_state_before.action_stats).length > 0
              ? Object.entries(step.agent_state_before.action_stats).map(([name, value]) => (
                <div className="compact-row" key={name}>
                  <b>{name}</b>
                  <span>{value.trials}</span>
                  <span>{value.cumulative_information_reward}</span>
                  <span>{value.mean_information_reward}</span>
                </div>
              ))
              : <div className="empty-row">尚无动作历史</div>}
          </div>
        </div>
      </div>

      {/* Candidates */}
      <div className="data-section">
        <div className="data-section-head"><strong>本步全部候选</strong><span>{step.candidates.length} CANDIDATES</span></div>
        <div className="data-section-body">
          <div className="compact-table candidate-table">
            <div className="compact-head"><span>RANK</span><span>ACTION</span><span>DATA</span><span>SCORE</span><span>EVIDENCE</span></div>
            {step.candidates.length > 0
              ? step.candidates.map((candidate, idx) => (
                <div className={`compact-row ${idx === 0 ? 'chosen-row' : ''}`} key={`${candidate.action}-${idx}`}>
                  <span>{idx + 1}</span>
                  <b>{candidate.action}</b>
                  <CompactJson value={candidate.data} />
                  <strong>{candidate.score.toFixed(3)}</strong>
                  <span>{candidate.evidence}</span>
                </div>
              ))
              : <div className="empty-row">RESET 没有候选动作</div>}
          </div>
        </div>
      </div>

      {/* Perception / color histogram */}
      <div className="data-section">
        <div className="data-section-head"><strong>颜色直方图</strong><span>BACKGROUND {step.perception.background_color}</span></div>
        <div className="data-section-body">
          <div className="histogram-list">
            {step.perception.color_histogram.map((entry) => (
              <div key={entry.color}>
                <span className={`color-swatch color-${entry.color % 16}`} />
                <b>{entry.color}</b>
                <i style={{ width: `${Math.max(2, entry.count / (step.perception.width * step.perception.height) * 100)}%` }} />
                <em>{entry.count}</em>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Components */}
      <div className="data-section">
        <div className="data-section-head"><strong>连通区域 / 对象</strong><span>{step.perception.components.length} COMPONENTS</span></div>
        <div className="data-section-body">
          <div className="compact-table object-table">
            <div className="compact-head"><span>#</span><span>COLOR</span><span>SIZE</span><span>CENTER</span><span>BOUNDS</span></div>
            {step.perception.components.map((component) => (
              <div className="compact-row" key={component.id}>
                <span>{component.id}</span>
                <span><i className={`color-swatch color-${component.color % 16}`} />{component.color}</span>
                <b>{component.size}</b>
                <code>{component.center.x}, {component.center.y}</code>
                <code>{component.bounds.x_min},{component.bounds.y_min} → {component.bounds.x_max},{component.bounds.y_max}</code>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Action request / response */}
      <div className="vgi-data-duo">
        <div className="data-section">
          <div className="data-section-head"><strong>发出的请求</strong><span>REQUEST</span></div>
          <div className="data-section-body data-json-body">
            <CompactJson value={step.action_request} />
          </div>
        </div>
        <div className="data-section">
          <div className="data-section-head"><strong>环境返回</strong><span>RESPONSE</span></div>
          <div className="data-section-body data-json-body">
            <CompactJson value={step.environment_response} />
          </div>
        </div>
      </div>

      {/* Changed pixels */}
      {step.changed_pixels.length > 0 && (
        <div className="data-section">
          <div className="data-section-head"><strong>变化像素</strong><span>{step.changed_pixels.length} PIXELS</span></div>
          <div className="data-section-body">
            <div className="pixel-change-list">
              {step.changed_pixels.slice(0, 50).map((pixel, idx) => (
                <code key={idx}>({pixel.x},{pixel.y}) {pixel.before}→{pixel.after}</code>
              ))}
              {step.changed_pixels.length > 50 && <span className="empty-row">… 还有 {step.changed_pixels.length - 50} 个变化像素</span>}
            </div>
          </div>
        </div>
      )}

      {/* Click exploration queue */}
      <div className="data-section">
        <div className="data-section-head"><strong>点击探索队列</strong><span>{step.agent_state_before.pending_click_candidates.length} PENDING</span></div>
        <div className="data-section-body data-json-body">
          <CompactJson value={{ pending: step.agent_state_before.pending_click_candidates, used: step.agent_state_before.used_clicks }} />
        </div>
      </div>

      {/* Raw frame layers */}
      {step.raw_frame_layers.length > 0 && (
        <div className="data-section">
          <div className="data-section-head"><strong>原始帧图层</strong><span>{step.raw_frame_layers.length} LAYERS</span></div>
          <div className="data-section-body">
            <details className="cj-details">
              <summary className="cj-summary">展开 {step.raw_frame_layers.length} 个图层（矩阵）</summary>
              <div className="layer-strip">
                {step.raw_frame_layers.map((layer, idx) => (
                  <div className="layer-item" key={idx}>
                    <span>LAYER {idx}</span>
                    <PixelGrid frame={layer} label={`原始图层 ${idx}`} />
                  </div>
                ))}
              </div>
            </details>
          </div>
        </div>
      )}

      {/* Full raw event */}
      <div className="data-section">
        <div className="data-section-head"><strong>完整事件</strong><span>RAW</span></div>
        <div className="data-section-body data-json-body">
          <details className="cj-details">
            <summary className="cj-summary">展开完整事件 JSON</summary>
            <pre className="raw-event">{JSON.stringify(step, null, 2)}</pre>
          </details>
        </div>
      </div>
    </div>
  )
}
