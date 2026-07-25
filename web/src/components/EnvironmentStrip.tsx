import { Search } from 'lucide-react'
import type { GameInfo, GameRun, RunStatus } from '../types'

function statusClass(status?: RunStatus): string {
  switch (status) {
    case 'running': return 'status-running'
    case 'solved': return 'status-solved'
    case 'failed': return 'status-failed'
    case 'error': return 'status-error'
    case 'queued': return 'status-queued'
    case 'starting': return 'status-starting'
    case 'limit': return 'status-limit'
    case 'completed': return 'status-completed'
    case 'stopped': return 'status-stopped'
    default: return 'status-idle'
  }
}

function shortLabel(gameId: string): string {
  return gameId.slice(0, 2)
}

interface EnvironmentStripProps {
  games: GameInfo[]
  runs: Record<string, GameRun>
  selectedGameId: string
  query: string
  onQuery: (value: string) => void
  onSelect: (gameId: string) => void
}

export function EnvironmentStrip({ games, runs, selectedGameId, query, onQuery, onSelect }: EnvironmentStripProps) {
  const visible = games.filter((game) => game.game_id.includes(query.toLowerCase()))

  return (
    <div className="env-strip-wrapper">
      <label className="env-search">
        <Search size={12} />
        <input
          value={query}
          onChange={(event) => onQuery(event.target.value)}
          placeholder="id…"
          aria-label="搜索环境"
        />
      </label>
      <div className="env-strip" role="tablist" aria-label="环境列表">
        {visible.map((game) => {
          const run = runs[game.game_id]
          const status = run?.status
          const isSelected = selectedGameId === game.game_id
          const progress = run?.win_levels ? run.levels_completed / run.win_levels : 0

          return (
            <button
              key={game.game_id}
              className={`env-square ${statusClass(status)} ${isSelected ? 'selected' : ''}`}
              role="tab"
              aria-selected={isSelected}
              onClick={() => onSelect(game.game_id)}
              title={`${game.game_id} · ${game.official_game_id}\n${status ?? 'idle'}${run ? ` · ${run.action_count} actions · ${Math.round(progress * 100)}%` : ''}`}
            >
              {shortLabel(game.game_id)}
              {run && progress > 0 && <i className="env-progress" style={{ width: `${Math.min(100, progress * 100)}%` }} />}
            </button>
          )
        })}
      </div>
    </div>
  )
}
