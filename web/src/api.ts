import type { GameInfo, SuiteRun } from './types'

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

export async function createRun(gameIds: string[], maxActions: number): Promise<SuiteRun> {
  const response = await fetch(`${API_BASE}/runs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      game_ids: gameIds,
      max_actions: maxActions,
      agent: 'Heuristic Explorer',
    }),
  })
  return readJson<SuiteRun>(response)
}

export async function fetchRun(runId: string): Promise<SuiteRun> {
  const response = await fetch(`${API_BASE}/runs/${runId}`)
  return readJson<SuiteRun>(response)
}
