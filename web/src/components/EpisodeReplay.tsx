import { useEffect, useMemo, useState } from 'react'
import { AlertTriangle, RefreshCw } from 'lucide-react'
import { fetchEpisode } from '../api'
import type { TrainingEpisodeDetail, TrainingEpisodeStep } from '../types'
import { DecisionCard } from './DecisionCard'
import { ImaginationView } from './ImaginationView'

interface EpisodeReplayProps {
  episodeId: string | null
}

function surprise(step: TrainingEpisodeStep): number {
  return Math.max(0, Math.min(1, step.surprise?.value ?? 0))
}

export function EpisodeReplay({ episodeId }: EpisodeReplayProps) {
  const [episode, setEpisode] = useState<TrainingEpisodeDetail | null>(null)
  const [selectedIndex, setSelectedIndex] = useState(0)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!episodeId) return
    fetchEpisode(episodeId)
      .then((payload) => {
        setError(null)
        setEpisode(payload)
        const hotIndex = payload.steps.findIndex((step) => surprise(step) >= 0.3)
        setSelectedIndex(hotIndex >= 0 ? hotIndex : 0)
      })
      .catch((reason: Error) => setError(reason.message))
  }, [episodeId])

  const selected = useMemo(() => {
    if (!episode?.steps.length) return null
    return episode.steps[Math.min(selectedIndex, episode.steps.length - 1)]
  }, [episode, selectedIndex])

  if (!episodeId) {
    return (
      <section className="episode-replay empty">
        <span>选择一个 episode 查看逐步回放。</span>
      </section>
    )
  }

  if (error) {
    return (
      <section className="episode-replay empty error">
        <AlertTriangle size={16} />
        <span>{error}</span>
      </section>
    )
  }

  if (!episode || !selected) {
    return (
      <section className="episode-replay empty">
        <RefreshCw size={16} className="spin" />
        <span>读取 episode…</span>
      </section>
    )
  }

  return (
    <section className="episode-replay">
      <header className="episode-head">
        <div>
          <span className="section-label">EPISODE REPLAY</span>
          <h3>{episode.episode_id}</h3>
        </div>
        <div className="episode-tags">
          <span>{episode.trap}</span>
          <span>{episode.solved ? 'solved' : 'unsolved'}</span>
          <span>fool {episode.fool_score.toFixed(2)}</span>
        </div>
      </header>

      <ImaginationView step={selected} />

      <div className="episode-step-strip">
        {episode.steps.map((step, index) => (
          <button
            key={step.index}
            className={`${index === selectedIndex ? 'selected' : ''} ${surprise(step) >= 0.3 ? 'hot' : ''}`}
            onClick={() => setSelectedIndex(index)}
            title={`step ${step.index} surprise ${surprise(step).toFixed(2)}`}
          >
            <b>{step.index}</b>
            <i style={{ height: `${Math.max(8, surprise(step) * 48)}px` }} />
            {step.surprise?.belief_flips?.length ? <em>⚡</em> : null}
          </button>
        ))}
      </div>

      <DecisionCard step={selected} />
    </section>
  )
}
