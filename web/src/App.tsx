import { useCallback, useEffect, useMemo, useState } from 'react'
import { Activity, Bot, ChevronDown, Circle, Cloud, FlaskConical, Play, RefreshCw, Wifi, WifiOff } from 'lucide-react'
import { createRun, fetchGames, fetchRun } from './api'
import { buildDemoGameRun, buildDemoSuite, demoGames } from './demo'
import type { GameInfo, SuiteRun } from './types'
import { EventDetail, type DetailTab } from './components/EventDetail'
import { GameRail } from './components/GameRail'
import { PixelGrid } from './components/PixelGrid'
import { Timeline } from './components/Timeline'
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
  const [detailTab, setDetailTab] = useState<DetailTab>('trajectory')
  const [maxActions, setMaxActions] = useState(40)
  const [starting, setStarting] = useState(false)
  const [error, setError] = useState<string | null>(null)

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
      const nextRun = await createRun(ids, maxActions)
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

  const progress = selectedGame.win_levels
    ? Math.round((selectedGame.levels_completed / selectedGame.win_levels) * 100)
    : 0
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
        <div className="topbar-spacer" />
        <div className={`connection connection-${connection}`}>
          {connection === 'live' ? <Wifi size={14} /> : connection === 'demo' ? <WifiOff size={14} /> : <RefreshCw size={14} className="spin" />}
          {connection === 'live' ? 'Official / live' : connection === 'demo' ? 'Demo replay' : 'Connecting'}
        </div>
        <div className="agent-select"><Bot size={15} /><span>Heuristic Explorer</span><ChevronDown size={13} /></div>
        <label className="limit-select">上限<select value={maxActions} onChange={(event) => setMaxActions(Number(event.target.value))}><option value={20}>20</option><option value={40}>40</option><option value={80}>80</option></select></label>
        <button className="primary-action" onClick={startOfficialRun} disabled={starting}>
          {starting ? <RefreshCw size={15} className="spin" /> : <Play size={15} />}
          运行勾选 {checked.size || 1}
        </button>
      </header>

      <main className="workspace">
        <GameRail
          games={games}
          runs={run.games}
          selectedGameId={selectedGameId}
          checked={checked}
          query={query}
          onQuery={setQuery}
          onSelect={selectGame}
          onToggle={toggleChecked}
        />

        <div className="center-column">
          <section className="game-stage">
            <div className="stage-header">
              <div className="stage-title">
                <div className={`run-indicator ${selectedGame.status === 'running' ? 'is-running' : ''}`}><Circle size={8} fill="currentColor" /></div>
                <div><span className="section-label">GAME DETAIL</span><h1>{selectedGameId}<small>{selectedGame.official_game_id}</small></h1></div>
              </div>
              <div className="stage-stats">
                <div><span>STATE</span><b>{selectedGame.state.replace('_', ' ')}</b></div>
                <div><span>LEVEL</span><b>{selectedGame.levels_completed}<i>/ {selectedGame.win_levels || '—'}</i></b></div>
                <div><span>ACTIONS</span><b>{selectedGame.action_count}</b></div>
                <div><span>PROGRESS</span><b>{progress}%</b></div>
              </div>
            </div>
            <div className="frame-area">
              <div className="frame-corners" aria-hidden="true" />
              {selectedStep ? (
                <PixelGrid
                  frame={selectedStep.frame}
                  beforeFrame={selectedStep.before_frame}
                  showDiff={detailTab === 'diff'}
                  label={`${selectedGameId} 第 ${selectedStep.index} 帧`}
                />
              ) : (
                <div className="frame-loading"><Activity size={22} /><span>等待官方环境首帧</span></div>
              )}
              <div className="frame-labels"><span>64 × 64 OBSERVATION</span><span>FRAME {String(selectedStep?.index ?? 0).padStart(3, '0')}</span></div>
            </div>
            <Timeline
              steps={steps}
              selectedIndex={safeIndex}
              playing={playing}
              speed={speed}
              onPlaying={setPlaying}
              onSelect={selectStep}
              onSpeed={setSpeed}
            />
          </section>
          <EventDetail
            steps={steps}
            selectedIndex={safeIndex}
            tab={detailTab}
            onTab={setDetailTab}
            onSelect={selectStep}
          />
        </div>

        <TraceInspector step={selectedStep} />
      </main>

      <footer className="statusbar">
        <span><Cloud size={12} />{connection === 'live' ? 'anonymous official access' : 'local demo fixture'}</span>
        <span><FlaskConical size={12} />{games.length} environments</span>
        <span><Activity size={12} />{runningGames} running</span>
        <span>{completedGames} solved</span>
        <span className="statusbar-spacer" />
        {error && <span className="footer-error">{error}</span>}
        <span>ARC3 audit schema v1</span>
      </footer>
    </div>
  )
}
