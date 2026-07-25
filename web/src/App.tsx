import { useCallback, useEffect, useMemo, useState } from 'react'
import { Activity, Cloud, FlaskConical, HelpCircle, RefreshCw, Wifi, WifiOff } from 'lucide-react'
import { createRun, fetchGames, fetchRun } from './api'
import { buildDemoGameRun, buildDemoSuite, demoGames } from './demo'
import type { AgentStrategyId, GameInfo, HistoryViewMode, InterfaceMode, SuiteRun } from './types'
import { AGENT_STRATEGIES } from './types'
import { EnvironmentStrip } from './components/EnvironmentStrip'
import { AgentControls } from './components/AgentControls'
import { VisualGameInterface } from './components/VisualGameInterface'
import { FrameHistory } from './components/FrameHistory'
import { TraceInspector } from './components/TraceInspector'
import { EventDetail, type DetailTab } from './components/EventDetail'
import { HelpDrawer } from './components/HelpDrawer'
import { TrainingDashboard } from './components/TrainingDashboard'

const terminalStatuses = new Set(['completed', 'stopped', 'error'])

export default function App() {
  const [games, setGames] = useState<GameInfo[]>(demoGames)
  const [run, setRun] = useState<SuiteRun>(() => buildDemoSuite())
  const [connection, setConnection] = useState<'connecting' | 'live' | 'demo'>('connecting')
  const [selectedGameId, setSelectedGameId] = useState('ls20')
  const [query, setQuery] = useState('')
  const [selectedIndex, setSelectedIndex] = useState(7)
  const [followLive, setFollowLive] = useState(true)
  const [playing, setPlaying] = useState(false)
  const [speed, setSpeed] = useState(1)
  const [maxActions, setMaxActions] = useState(40)
  const [starting, setStarting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Visual-game interface state
  const [interfaceMode, setInterfaceMode] = useState<InterfaceMode>('visual')
  const [historyView, setHistoryView] = useState<HistoryViewMode>('gallery')
  const [selectedStrategy, setSelectedStrategy] = useState<AgentStrategyId>('transform-aware')
  const [showDiff, setShowDiff] = useState(false)
  const [detailTab, setDetailTab] = useState<DetailTab | null>(null)
  const [helpOpen, setHelpOpen] = useState(false)
  const [appMode, setAppMode] = useState<'run' | 'training'>('run')

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
    setShowDiff(false)
  }, [run.games])

  const selectStep = (index: number) => {
    setSelectedIndex(index)
    setFollowLive(index >= steps.length - 1)
  }

  const toggleDetailTab = (tab: DetailTab) => {
    setDetailTab((current) => current === tab ? null : tab)
  }

  const strategyLabel = (id: AgentStrategyId): string => {
    return AGENT_STRATEGIES.find((s) => s.id === id)?.label ?? 'Heuristic Explorer'
  }

  const startOfficialRun = async () => {
    setStarting(true)
    setError(null)
    try {
      const nextRun = await createRun([selectedGameId], maxActions, strategyLabel(selectedStrategy))
      setRun(nextRun)
      setConnection('live')
      setSelectedGameId(selectedGameId)
      setSelectedIndex(0)
      setFollowLive(true)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '无法启动官方运行')
      setConnection('demo')
    } finally {
      setStarting(false)
    }
  }

  const startRerun = async () => {
    // Re-run the current environment: create a new run for just this game
    setError(null)
    setStarting(true)
    try {
      const nextRun = await createRun([selectedGameId], maxActions, strategyLabel(selectedStrategy))
      setRun(nextRun)
      setConnection('live')
      setSelectedIndex(0)
      setFollowLive(true)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '重玩失败，回退演示模式')
      // In demo mode, simulate a rerun by resetting the demo suite
      setRun(buildDemoSuite())
      setSelectedIndex(0)
    } finally {
      setStarting(false)
    }
  }

  const runningGames = Object.values(run.games).filter((game) => game.status === 'running').length
  const completedGames = Object.values(run.games).filter((game) => game.status === 'solved').length

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand"><span className="brand-mark">A3</span><strong>ARC3 RUNNER</strong></div>
        <div className="topbar-divider" />
        <div className="run-context">
          <span className="section-label">ACTIVE SESSION</span>
          <b>{run.run_id}</b>
        </div>

        <div className="app-mode-toggle">
          <button className={appMode === 'run' ? 'active' : ''} onClick={() => setAppMode('run')}>运行</button>
          <button className={appMode === 'training' ? 'active' : ''} onClick={() => setAppMode('training')}>训练</button>
        </div>

        {appMode === 'run' && (
          <EnvironmentStrip
            games={games}
            runs={run.games}
            selectedGameId={selectedGameId}
            query={query}
            onQuery={setQuery}
            onSelect={selectGame}
          />
        )}

        <div className={`connection connection-${connection}`}>
          {connection === 'live' ? <Wifi size={14} /> : connection === 'demo' ? <WifiOff size={14} /> : <RefreshCw size={14} className="spin" />}
          {connection === 'live' ? 'Official / live' : connection === 'demo' ? 'Demo replay' : 'Connecting'}
        </div>

        <button className="help-button" onClick={() => setHelpOpen(true)} aria-label="打开界面导览" title="界面导览">
          <HelpCircle size={15} />
        </button>

        {appMode === 'run' && (
          <AgentControls
            strategy={selectedStrategy}
            maxActions={maxActions}
            onStrategy={setSelectedStrategy}
            onMaxActions={setMaxActions}
            onStart={startOfficialRun}
            starting={starting}
          />
        )}
      </header>

      {appMode === 'run' ? (
        <main className="workspace">
          {/* Center column: VisualGameInterface + FrameHistory */}
          <div className="center-column">
            <VisualGameInterface
              step={selectedStep}
              stepIndex={safeIndex}
              totalSteps={Math.max(0, steps.length - 1)}
              gameId={selectedGameId}
              levelsCompleted={selectedGame.levels_completed}
              winLevels={selectedGame.win_levels}
              actionCount={selectedGame.action_count}
              stateLabel={selectedGame.state.replace('_', ' ')}
              gameStatus={selectedGame.status}
              interfaceMode={interfaceMode}
              onMode={setInterfaceMode}
              showDiff={showDiff}
              onDiffToggle={() => setShowDiff((d) => !d)}
            />

            <EventDetail
              steps={steps}
              selectedIndex={safeIndex}
              tab={detailTab}
              onTab={toggleDetailTab}
              onSelect={selectStep}
            />

            <FrameHistory
              steps={steps}
              selectedIndex={safeIndex}
              playing={playing}
              speed={speed}
              viewMode={historyView}
              onViewMode={setHistoryView}
              onPlaying={setPlaying}
              onSelect={selectStep}
              onSpeed={setSpeed}
              onRerun={startRerun}
              canRerun={steps.length > 0}
            />
          </div>

          {/* Right panel: TraceInspector (decision audit detail) */}
          <TraceInspector step={selectedStep} />
        </main>
      ) : (
        <main className="workspace training-workspace">
          <TrainingDashboard />
        </main>
      )}

      <footer className="statusbar">
        <span><Cloud size={12} />{connection === 'live' ? 'anonymous official access' : 'local demo fixture'}</span>
        <span><FlaskConical size={12} />{games.length} environments</span>
        <span><Activity size={12} />{runningGames} running</span>
        <span>{completedGames} solved</span>
        <span className="statusbar-spacer" />
        {error && <span className="footer-error">{error}</span>}
        <span>ARC3 audit schema v3</span>
      </footer>
      <HelpDrawer open={helpOpen} onClose={() => setHelpOpen(false)} />
    </div>
  )
}
