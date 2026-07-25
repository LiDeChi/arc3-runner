import { Bot, Play, RefreshCw } from 'lucide-react'
import { AGENT_STRATEGIES, type AgentStrategyId } from '../types'

interface AgentControlsProps {
  strategy: AgentStrategyId
  maxActions: number
  onStrategy: (id: AgentStrategyId) => void
  onMaxActions: (value: number) => void
  onStart: () => void
  starting: boolean
}

export function AgentControls({ strategy, maxActions, onStrategy, onMaxActions, onStart, starting }: AgentControlsProps) {
  const selectedDescription = AGENT_STRATEGIES.find((s) => s.id === strategy)?.description

  return (
    <div className="agent-controls">
      <div className="agent-select">
        <Bot size={15} />
        <select
          value={strategy}
          onChange={(event) => onStrategy(event.target.value as AgentStrategyId)}
          aria-label="策略选择"
          title={selectedDescription}
        >
          {AGENT_STRATEGIES.map((s) => (
            <option key={s.id} value={s.id} title={s.description}>
              {s.label}
            </option>
          ))}
        </select>
      </div>
      <label className="limit-select">
        上限
        <select value={maxActions} onChange={(event) => onMaxActions(Number(event.target.value))}>
          <option value={20}>20</option>
          <option value={40}>40</option>
          <option value={80}>80</option>
        </select>
      </label>
      <button className="primary-action" onClick={onStart} disabled={starting}>
        {starting ? <RefreshCw size={15} className="spin" /> : <Play size={15} />}
        运行当前
      </button>
    </div>
  )
}
