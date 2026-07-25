import type {
  AgentStrategyId,
  GameInfo,
  SuiteRun,
  SynthGameSummary,
  SynthSpec,
  TrainingEpisodeDetail,
  TrainingEpisodeSummary,
  TrainingGeneration,
  TrainingKnowledge,
  TrainingStartParams,
  TrainingStatus,
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

export async function createRun(gameIds: string[], maxActions: number, agentId?: AgentStrategyId): Promise<SuiteRun> {
  const response = await fetch(`${API_BASE}/runs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      game_ids: gameIds,
      max_actions: maxActions,
      agent: agentId ?? 'heuristic-explorer',
    }),
  })
  return readJson<SuiteRun>(response)
}

export async function fetchRun(runId: string): Promise<SuiteRun> {
  const response = await fetch(`${API_BASE}/runs/${runId}`)
  return readJson<SuiteRun>(response)
}

export async function fetchSynthSpecs(): Promise<SynthSpec[]> {
  const response = await fetch(`${API_BASE}/synth/specs`)
  const payload = await readJson<{ specs: SynthSpec[] }>(response)
  return payload.specs
}

export async function createSynthSpec(template: string, params: Record<string, unknown>): Promise<SynthSpec> {
  const response = await fetch(`${API_BASE}/synth/specs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ template, params }),
  })
  return readJson<SynthSpec>(response)
}

export async function startTraining(params: TrainingStartParams): Promise<TrainingStatus> {
  const response = await fetch(`${API_BASE}/training/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  })
  return readJson<TrainingStatus>(response)
}

export async function stopTraining(): Promise<TrainingStatus> {
  const response = await fetch(`${API_BASE}/training/stop`, { method: 'POST' })
  return readJson<TrainingStatus>(response)
}

export async function fetchTrainingStatus(): Promise<TrainingStatus> {
  const response = await fetch(`${API_BASE}/training/status`)
  return readJson<TrainingStatus>(response)
}

export async function fetchTrainingGenerations(): Promise<TrainingGeneration[]> {
  const response = await fetch(`${API_BASE}/training/generations`)
  return readJson<TrainingGeneration[]>(response)
}

export async function fetchTrainingKnowledge(): Promise<TrainingKnowledge> {
  const response = await fetch(`${API_BASE}/training/knowledge`)
  return readJson<TrainingKnowledge>(response)
}

export async function fetchTrainingGenerationGames(gen: number): Promise<SynthGameSummary[]> {
  const response = await fetch(`${API_BASE}/training/generations/${gen}/games`)
  return readJson<SynthGameSummary[]>(response)
}

export async function fetchTrainingGenerationEpisodes(gen: number): Promise<TrainingEpisodeSummary[]> {
  const response = await fetch(`${API_BASE}/training/generations/${gen}/episodes`)
  return readJson<TrainingEpisodeSummary[]>(response)
}

export async function fetchTrainingEpisode(episodeId: string): Promise<TrainingEpisodeDetail> {
  const response = await fetch(`${API_BASE}/training/episodes/${episodeId}`)
  return readJson<TrainingEpisodeDetail>(response)
}
