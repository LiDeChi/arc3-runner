import type {
  GameInfo,
  SuiteRun,
  TrainingEpisodeDetail,
  TrainingEpisodeSummary,
  TrainingGenerationMetrics,
  TrainingKnowledge,
  TrainingStartParams,
} from './types'

const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://127.0.0.1:8010/api'

async function readJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: response.statusText }))
    throw new Error(payload.detail ?? `HTTP ${response.status}`)
  }
  return response.json() as Promise<T>
}

export async function fetchGames(): Promise<GameInfo[]> {
  const response = await fetch(`${API_BASE}/games`)
  const payload = await readJson<{ games: GameInfo[] }>(response)
  return payload.games
}

export async function createRun(gameIds: string[], maxActions: number, agent?: string): Promise<SuiteRun> {
  const response = await fetch(`${API_BASE}/runs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      game_ids: gameIds,
      max_actions: maxActions,
      agent: agent ?? 'Heuristic Explorer',
    }),
  })
  return readJson<SuiteRun>(response)
}

export async function fetchRun(runId: string): Promise<SuiteRun> {
  const response = await fetch(`${API_BASE}/runs/${runId}`)
  return readJson<SuiteRun>(response)
}

export async function startTraining(params: TrainingStartParams): Promise<TrainingGenerationMetrics[]> {
  const response = await fetch(`${API_BASE}/training/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  })
  const payload = await readJson<{ generations: TrainingGenerationMetrics[] }>(response)
  return payload.generations
}

export async function fetchTrainingGenerations(): Promise<TrainingGenerationMetrics[]> {
  const response = await fetch(`${API_BASE}/training/generations`)
  const payload = await readJson<{ generations: TrainingGenerationMetrics[] }>(response)
  return payload.generations
}

export async function fetchGenerationEpisodes(gen: number): Promise<TrainingEpisodeSummary[]> {
  const response = await fetch(`${API_BASE}/training/generations/${gen}/episodes`)
  const payload = await readJson<{ episodes: TrainingEpisodeSummary[] }>(response)
  return payload.episodes
}

export async function fetchEpisode(episodeId: string): Promise<TrainingEpisodeDetail> {
  const response = await fetch(`${API_BASE}/training/episodes/${episodeId}`)
  return readJson<TrainingEpisodeDetail>(response)
}

export async function fetchTrainingKnowledge(): Promise<TrainingKnowledge> {
  const response = await fetch(`${API_BASE}/training/knowledge`)
  return readJson<TrainingKnowledge>(response)
}
