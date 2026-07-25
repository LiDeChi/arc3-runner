import type {
  ArcEvent,
  CalibrationData,
  EpisodeSummary,
  GameSpec,
  MetricPoint,
  RunSummary,
  TrapDatum
} from "./types";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "/api";

function pathUrl(path: string): string {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  if (API_BASE.startsWith("http://") || API_BASE.startsWith("https://")) {
    return `${API_BASE.replace(/\/$/, "")}${normalizedPath}`;
  }
  return `${API_BASE.replace(/\/$/, "")}${normalizedPath}`;
}

export function websocketUrl(runId: string): string {
  const encodedRun = encodeURIComponent(runId);
  const path = `${API_BASE.replace(/\/$/, "")}/ws/runs/${encodedRun}`;

  if (path.startsWith("http://") || path.startsWith("https://")) {
    return path.replace(/^http/, "ws");
  }

  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}${path}`;
}

async function jsonFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(pathUrl(path), {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {})
    },
    ...init
  });

  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`);
  }

  return (await response.json()) as T;
}

function asArray<T>(value: unknown, key: string): T[] {
  if (Array.isArray(value)) return value as T[];
  if (value && typeof value === "object" && Array.isArray((value as Record<string, unknown>)[key])) {
    return (value as Record<string, unknown>)[key] as T[];
  }
  return [];
}

export function normalizeEvent(raw: unknown): ArcEvent {
  const record = raw as Record<string, unknown>;
  const payload =
    typeof record.payload_json === "string"
      ? JSON.parse(record.payload_json)
      : record.payload ?? {};

  return {
    id: typeof record.id === "number" ? record.id : undefined,
    episode_id: String(record.episode_id ?? ""),
    step_idx: Number(record.step_idx ?? (payload as Record<string, unknown>).step_idx ?? 0),
    type: String(record.type ?? ""),
    payload: payload as Record<string, unknown>
  };
}

export const api = {
  async createRun(body: Record<string, unknown>): Promise<{ run_id: string; id: string }> {
    return jsonFetch<{ run_id: string; id: string }>("/runs", {
      method: "POST",
      body: JSON.stringify(body)
    });
  },

  async getRuns(): Promise<RunSummary[]> {
    const data = await jsonFetch<unknown>("/runs");
    return asArray<RunSummary>(data, "runs");
  },

  async getRun(runId: string): Promise<RunSummary> {
    return jsonFetch<RunSummary>(`/runs/${encodeURIComponent(runId)}`);
  },

  async pauseRun(runId: string): Promise<void> {
    await jsonFetch(`/runs/${encodeURIComponent(runId)}/pause`, { method: "POST" });
  },

  async resumeRun(runId: string): Promise<void> {
    await jsonFetch(`/runs/${encodeURIComponent(runId)}/resume`, { method: "POST" });
  },

  async getEpisodes(runId: string, limit = 50, offset = 0): Promise<EpisodeSummary[]> {
    const data = await jsonFetch<unknown>(
      `/runs/${encodeURIComponent(runId)}/episodes?limit=${limit}&offset=${offset}`
    );
    return asArray<EpisodeSummary>(data, "episodes");
  },

  async getEvents(episodeId: string, afterId?: number): Promise<ArcEvent[]> {
    const suffix = afterId ? `?after_id=${afterId}` : "";
    const data = await jsonFetch<unknown>(`/episodes/${encodeURIComponent(episodeId)}/events${suffix}`);
    return asArray<unknown>(data, "events").map(normalizeEvent);
  },

  async getMetrics(runId: string, names: string[]): Promise<MetricPoint[]> {
    const data = await jsonFetch<unknown>(
      `/runs/${encodeURIComponent(runId)}/metrics?names=${encodeURIComponent(names.join(","))}`
    );
    const rows = asArray<MetricPoint>(data, "metrics");

    if (rows.length && rows[0].name) {
      const byEpisode = new Map<number, MetricPoint>();
      for (const row of rows) {
        const episodeIdx = Number(row.episode_idx);
        const current = byEpisode.get(episodeIdx) ?? { episode_idx: episodeIdx };
        if (row.name && typeof row.value === "number") {
          current[row.name] = row.value;
        }
        byEpisode.set(episodeIdx, current);
      }
      return [...byEpisode.values()].sort((a, b) => a.episode_idx - b.episode_idx);
    }

    return rows.sort((a, b) => a.episode_idx - b.episode_idx);
  },

  async getCalibration(runId: string): Promise<CalibrationData> {
    const data = await jsonFetch<CalibrationData>(`/runs/${encodeURIComponent(runId)}/calibration`);
    return {
      bins: data.bins ?? [],
      high_conf_errors: data.high_conf_errors ?? []
    };
  },

  async getTraps(runId: string): Promise<TrapDatum[]> {
    const data = await jsonFetch<unknown>(`/runs/${encodeURIComponent(runId)}/traps`);
    return asArray<TrapDatum>(data, "traps");
  },

  async previewGame(seed: number): Promise<GameSpec> {
    return jsonFetch<GameSpec>("/games/preview", {
      method: "POST",
      body: JSON.stringify({
        seed,
        game_source: "adversarial"
      })
    });
  }
};
