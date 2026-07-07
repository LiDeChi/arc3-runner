import { useCallback, useEffect, useMemo, useState } from 'react'
import { Activity, Bot, Circle, Cloud, FlaskConical, Play, RefreshCw, Sidebar, Wifi, WifiOff } from 'lucide-react'
import { createRun, fetchGames, fetchRun } from './api'
import { buildDemoGameRun, buildDemoSuite, demoGames } from './demo'
import type { GameInfo, SuiteRun, AgentStrategyId, InterfaceMode, HistoryViewMode } from './types'
import { AGENT_STRATEGIES } from './types'
import { EnvironmentStrip } from './components/EnvironmentStrip'
import { VisualGameInterface } from './components/VisualGameInterface'
import { FrameHistory } from './components/FrameHistory'
import { TraceInspector } from './components/TraceInspector'

const terminalStatuses = new Set(['completed', 'stopped', 'error'])

export default function App() {
  const [games, setGames] = useState<GameInfo[]>(demoGames)
  const [run, setRun] = useState<SuiteRun>(() => buildDemoSuite())
  const [connection, setConnection] = useState<'connecting' | 'live' | 'demo'>('connecting')
  const [selectedGameId, setSelectedGameId] = useState('ls20')
  const [checked, setChecked] = useState<Set<string>>(() => new Set(['ls20', 'ft09', 'vc33']))
  const [query, setQuery] = useState('')
  const [selectedIndex, setSelectedIndex] = useState(7)
  const [followLive, setFollowLive] = useState(true)
  const [playing, setPlaying] = useState(false)
  const [speed, setSpeed] = useState(1)
  const [maxActions, setMaxActions] = useState(40)
  const [starting, setStarting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // New UI state
  const [interfaceMode, setInterfaceMode] = useState<InterfaceMode>('visual')
  const [historyViewMode, setHistoryViewMode] = useState<HistoryViewMode>('gallery')
  const [strategyId, setStrategyId] = useState<AgentStrategyId>('heuristic-explorer')
  const [showInspector, setShowInspector] = useState(false)

  useEffect(() => {
    fetchGames()
      .then((officialGames) => {
        setGames(officialGames)
        setConnection('live')
      })
      .catch(() => setConnection('demo'))
  }, [])

  useEffect(() => {
    if (run.mode !== 'official-live' || terminalStatuses.has(run.status)) return
    const timer = window.setInterval(() => {
      fetchRun(run.run_id)
        .then((nextRun) => {
          setRun(nextRun)
          if (nextRun.current_game_id && nextRun.games[nextRun.current_game_id]?.steps.length) {
            setSelectedGameId(nextRun.current_game_id)
            if (followLive) {
              setSelectedIndex(nextRun.games[nextRun.current_game_id].steps.length - 1)
            }
          }
        })
        .catch((reason: Error) => setError(reason.message))
    }, 700)
    return () => window.clearInterval(timer)
  }, [followLive, run.mode, run.run_id, run.status])

  const selectedGame = useMemo(() => {
    return run.games[selectedGameId] ?? buildDemoGameRun(selectedGameId)
  }, [run.games, selectedGameId])
  const steps = selectedGame.steps
  const safeIndex = Math.min(selectedIndex, Math.max(0, steps.length - 1))
  const selectedStep = steps[safeIndex]

  useEffect(() => {
    if (!playing || steps.length < 2) return
    const timer = window.setInterval(() => {
      setSelectedIndex((current) => {
        if (current >= steps.length - 1) {
          setPlaying(false)
          return current
        }
        return current + 1
      })
    }, 720 / speed)
    return () => window.clearInterval(timer)
  }, [playing, speed, steps.length])

  const selectGame = useCallback((gameId: string) => {
    setSelectedGameId(gameId)
    const length = run.games[gameId]?.steps.length ?? buildDemoGameRun(gameId).steps.length
    setSelectedIndex(Math.max(0, length - 1))
    setPlaying(false)
    setFollowLive(true)
  }, [run.games])

  const selectStep = (index: number) => {
    setSelectedIndex(index)
    setFollowLive(index >= steps.length - 1)
  }

  const toggleChecked = (gameId: string) => {
    setChecked((current) => {
      const next = new Set(current)
      if (next.has(gameId)) next.delete(gameId)
      else next.add(gameId)
      return next
    })
  }

  const startOfficialRun = async () => {
    const ids = checked.size ? [...checked] : [selectedGameId]
    setStarting(true)
    setError(null)
    try {
      const nextRun = await createRun(ids, maxActions, strategyId)
      setRun(nextRun)
      setConnection('live')
      setSelectedGameId(ids[0])
      setSelectedIndex(0)
      setFollowLive(true)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '无法启动官方运行')
      setConnection('demo')
    } finally {
      setStarting(false)
    }
  }

  const handleRerun = async (gameId: string) => {
    setStarting(true)
    setError(null)
    try {
      const nextRun = await createRun([gameId], maxActions, strategyId)
      setRun(nextRun)
      setSelectedGameId(gameId)
      setSelectedIndex(0)
      setFollowLive(true)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '重玩失败')
    } finally {
      setStarting(false)
    }
  }

  const progress = selectedGame.win_levels
    ? Math.round((selectedGame.levels_completed / selectedGame.win_levels) * 100)
    : 0
  const runningGames = Object.values(run.games).filter((game) => game.status === 'running').length
  const completedGames = Object.values(run.games).filter((game) => game.status === 'solved').length

  return (
    <div className="app-shell">
      <header className={`topbar ${showInspector ? 'has-inspector' : ''}`}>
        <div className="brand"><span className="brand-mark">A3</span><strong>ARC3 RUNNER</strong></div>
        <div className="topbar-divider" />
        <div className="run-context">
          <span className="section-label">ACTIVE SESSION</span>
          <b>{run.run_id}</b>
        </div>

        <div className="env-strip-area">
          <EnvironmentStrip
            games={games}
            runs={run.games}
            selectedGameId={selectedGameId}
            checked={checked}
            query={query}
            onQuery={setQuery}
            onSelect={selectGame}
            onToggle={toggleChecked}
          />
        </div>

        <div className="topbar-spacer" />
        <div className={`connection connection-${connection}`}>
          {connection === 'live' ? <Wifi size={13} /> : connection === 'demo' ? <WifiOff size={13} /> : <RefreshCw size={13} className="spin" />}
          {connection === 'live' ? 'Official' : connection === 'demo' ? 'Demo' : '···'}
        </div>

        <div className="agent-select">
          <Bot size={14} />
          <select value={strategyId} onChange={(event) => setStrategyId(event.target.value as AgentStrategyId)}>
            {AGENT_STRATEGIES.map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}
          </select>
        </div>

        <label className="limit-select">上限
          <select value={maxActions} onChange={(event) => setMaxActions(Number(event.target.value))}>
            <option value={20}>20</option><option value={40}>40</option><option value={80}>80</option>
          </select>
        </label>

        <button className="primary-action" onClick={startOfficialRun} disabled={starting}>
          {starting ? <RefreshCw size={14} className="spin" /> : <Play size={14} />}
          运行 {checked.size || 1}
        </button>
      </header>

      <main className={`workspace ${showInspector ? 'has-inspector' : ''}`}>
        <div className="main-content">
          <div className="game-stage-bar">
            <div className="stage-left">
              <div className={`run-indicator ${selectedGame.status === 'running' ? 'is-running' : ''}`}>
                <Circle size={7} fill="currentColor" />
              </div>
              <span className="section-label">GAME</span>
              <h2>{selectedGameId}</h2>
              <small>{selectedGame.official_game_id}</small>
            </div>
            <div className="stage-center">
              <span className="stage-pill">
                <span>状态</span><b>{selectedGame.state.replace(/_/g, ' ')}</b>
              </span>
              <span className="stage-pill">
                <span>关卡</span><b>{selectedGame.levels_completed}<i>/ {selectedGame.win_levels || '—'}</i></b>
              </span>
              <span className="stage-pill">
                <span>动作</span><b>{selectedGame.action_count}</b>
              </span>
              <span className="stage-pill">
                <span>进度</span><b>{progress}%</b>
              </span>
            </div>
            <div className="stage-right">
              <button className="rerun-btn" onClick={() => handleRerun(selectedGameId)} disabled={starting}>
                <RefreshCw size={12} /> 重玩
              </button>
              <button
                className={`inspector-toggle ${showInspector ? 'active' : ''}`}
                onClick={() => setShowInspector(!showInspector)}
                title="切换决策详情"
              >
                <Sidebar size={13} />
              </button>
            </div>
          </div>

          <VisualGameInterface
            step={selectedStep}
            gameId={selectedGameId}
            mode={interfaceMode}
            onModeChange={setInterfaceMode}
          />

          <FrameHistory
            steps={steps}
            selectedIndex={safeIndex}
            playing={playing}
            speed={speed}
            viewMode={historyViewMode}
            onPlaying={setPlaying}
            onSelect={selectStep}
            onSpeed={setSpeed}
            onViewMode={setHistoryViewMode}
          />
        </div>

        {showInspector && (
          <aside className="inspector-panel">
            <TraceInspector step={selectedStep} />
          </aside>
        )}
      </main>

      <footer className="statusbar">
        <span><Cloud size={11} />{connection === 'live' ? 'anonymous official' : 'local demo'}</span>
        <span><FlaskConical size={11} />{games.length} environments</span>
        <span><Activity size={11} />{runningGames} running</span>
        <span>{completedGames} solved</span>
        <span className="statusbar-spacer" />
        {error && <span className="footer-error">{error}</span>}
        <span>ARC3 v2</span>
      </footer>
    </div>
  )
}
