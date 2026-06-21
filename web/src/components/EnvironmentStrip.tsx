import { Search } from 'lucide-react'
import { useRef, useState } from 'react'
import type { GameInfo, GameRun } from '../types'

const statusColors: Record<string, string> = {
  idle: 'idle',
  queued: 'queued',
  starting: 'starting',
  running: 'running',
  solved: 'solved',
  failed: 'failed',
  limit: 'limit',
  error: 'error',
  completed: 'solved',
  stopped: 'stopped',
}

const statusLabel: Record<string, string> = {
  idle: '待运行', queued: '排队', starting: '连接', running: '运行',
  solved: '完成', failed: '失败', limit: '上限', error: '错误', stopped: '停止',
}

interface EnvironmentStripProps {
  games: GameInfo[]
  runs: Record<string, GameRun>
  selectedGameId: string
  checked: Set<string>
  query: string
  onQuery: (value: string) => void
  onSelect: (gameId: string) => void
  onToggle: (gameId: string) => void
}

export function EnvironmentStrip({ games, runs, selectedGameId, checked, query, onQuery, onSelect, onToggle }: EnvironmentStripProps) {
  const stripRef = useRef<HTMLDivElement>(null)
  const [showSearch, setShowSearch] = useState(false)
  const visible = games.filter((game) => game.game_id.includes(query.toLowerCase()))

  return (
    <div className="env-strip-wrapper">
      <div className="env-strip-scroll" ref={stripRef}>
        <div className="env-strip">
          {visible.map((game) => {
            const run = runs[game.game_id]
            const status: string = run?.status ?? 'idle'
            const isChecked = checked.has(game.game_id)
            const isSelected = selectedGameId === game.game_id
            const progress = run?.win_levels ? Math.round((run.levels_completed / run.win_levels) * 100) : 0
            return (
              <div
                key={game.game_id}
                className={`env-square env-${statusColors[status] ?? 'idle'} ${isChecked ? 'checked' : ''} ${isSelected ? 'selected' : ''}`}
                onClick={() => onSelect(game.game_id)}
                title={`${game.game_id} · ${statusLabel[status] ?? status}${run ? ` · ${run.action_count} actions · ${progress}%` : ''}`}
                role="button"
                tabIndex={0}
              >
                <div className="env-fill" style={{ height: `${Math.max(2, progress)}%` }} />
                <span
                  className="env-check"
                  onClick={(event) => { event.stopPropagation(); onToggle(game.game_id) }}
                >
                  {isChecked && <span className="env-check-mark">✓</span>}
                </span>
                <span className="env-label">{game.game_id.slice(0, 4)}</span>
              </div>
            )
          })}
        </div>
      </div>
      <div className={`env-actions ${showSearch ? 'show' : ''}`}>
        {showSearch ? (
          <div className="env-search-inline">
            <input
              value={query}
              onChange={(event) => onQuery(event.target.value)}
              placeholder="搜索..."
              autoFocus
              onBlur={() => { if (!query) setShowSearch(false) }}
              className="env-search-input"
            />
          </div>
        ) : (
          <button className="env-search-btn" onClick={() => setShowSearch(true)} title="搜索环境">
            <Search size={13} />
          </button>
        )}
        <span className="env-count">{games.length}</span>
      </div>
    </div>
  )
}
