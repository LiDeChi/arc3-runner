import { Check, CircleAlert, CircleDot, Search } from 'lucide-react'
import type { GameInfo, GameRun, RunStatus } from '../types'

const statusLabel: Record<string, string> = {
  queued: '排队', starting: '连接', running: '运行', solved: '完成', failed: '失败',
  limit: '上限', error: '错误', completed: '完成', stopped: '停止',
}

function StatusIcon({ status }: { status?: RunStatus }) {
  if (status === 'solved') return <Check size={13} />
  if (status === 'failed' || status === 'error') return <CircleAlert size={13} />
  return <CircleDot size={13} />
}

interface GameRailProps {
  games: GameInfo[]
  runs: Record<string, GameRun>
  selectedGameId: string
  checked: Set<string>
  query: string
  onQuery: (value: string) => void
  onSelect: (gameId: string) => void
  onToggle: (gameId: string) => void
}

export function GameRail({ games, runs, selectedGameId, checked, query, onQuery, onSelect, onToggle }: GameRailProps) {
  const visible = games.filter((game) => game.game_id.includes(query.toLowerCase()))
  return (
    <aside className="game-rail">
      <div className="rail-heading">
        <div>
          <span className="section-label">OFFICIAL SET</span>
          <strong>公开环境</strong>
        </div>
        <span className="count">{games.length}</span>
      </div>
      <label className="search-box">
        <Search size={14} />
        <input value={query} onChange={(event) => onQuery(event.target.value)} placeholder="搜索 game id" />
      </label>
      <div className="game-list">
        {visible.map((game) => {
          const run = runs[game.game_id]
          const status = run?.status
          const progress = run?.win_levels ? run.levels_completed / run.win_levels : 0
          return (
            <div
              className={`game-row ${selectedGameId === game.game_id ? 'selected' : ''}`}
              key={game.game_id}
              onClick={() => onSelect(game.game_id)}
              role="button"
              tabIndex={0}
              onKeyDown={(event) => event.key === 'Enter' && onSelect(game.game_id)}
            >
              <button
                className={`check-button ${checked.has(game.game_id) ? 'checked' : ''}`}
                aria-label={`${checked.has(game.game_id) ? '取消' : '选择'} ${game.game_id}`}
                onClick={(event) => {
                  event.stopPropagation()
                  onToggle(game.game_id)
                }}
              >
                {checked.has(game.game_id) && <Check size={11} />}
              </button>
              <div className="game-row-main">
                <div className="game-row-top">
                  <strong>{game.game_id}</strong>
                  <span className={`status status-${status ?? 'idle'}`}>
                    <StatusIcon status={status} /> {status ? statusLabel[status] : '待运行'}
                  </span>
                </div>
                <div className="game-row-meta">
                  <span>{game.tags[0] ?? 'logic'}</span>
                  <span>{run ? `${run.action_count} actions` : `${game.baseline_actions.length} levels`}</span>
                </div>
                <div className="mini-progress"><i style={{ width: `${Math.max(2, progress * 100)}%` }} /></div>
              </div>
            </div>
          )
        })}
      </div>
    </aside>
  )
}

