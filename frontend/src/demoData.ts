import type {
  ArcEvent,
  CalibrationData,
  EpisodeSummary,
  GameSpec,
  Grid,
  MetricPoint,
  RunSummary,
  TrapDatum
} from "./types";

function cloneGrid(grid: Grid): Grid {
  return grid.map((row) => [...row]);
}

function makeBaseTiles(): Grid {
  return Array.from({ length: 10 }, (_, y) =>
    Array.from({ length: 10 }, (_, x) => {
      if (x === 0 || y === 0 || x === 9 || y === 9) return 1;
      if (x === 8 && y === 1) return 2;
      if ((x === 4 && y > 1 && y < 8) || (y === 5 && x > 1 && x < 7)) return 1;
      return 0;
    })
  );
}

function withAgent(base: Grid, x: number, y: number): Grid {
  const grid = cloneGrid(base);
  grid[y][x] = 10;
  return grid;
}

const baseTiles = makeBaseTiles();

export const demoGameSpec: GameSpec = {
  id: "g03_mirror_demo",
  size: { w: 10, h: 10 },
  tiles: baseTiles,
  entities: [{ id: "agent", kind: "agent", x: 2, y: 7, color: 10 }],
  actions: {
    A1: { hint: "arrow_up" },
    A2: { hint: "arrow_down" },
    A3: { hint: "arrow_left" },
    A4: { hint: "arrow_right" },
    A5: { hint: "star" }
  },
  win: { type: "reach_goal" },
  max_steps: 100,
  meta: {
    traps: ["conjugate_mirror", "misleading_hint"],
    difficulty: 3.5,
    seed: 42
  }
};

const g0 = withAgent(baseTiles, 2, 7);
const g1Pred = withAgent(baseTiles, 2, 6);
const g1Actual = withAgent(baseTiles, 2, 8);
const g2Pred = withAgent(baseTiles, 2, 7);
const g2Actual = withAgent(baseTiles, 2, 7);
const g3Actual = withAgent(baseTiles, 3, 7);
const g4Actual = withAgent(baseTiles, 4, 7);

let eventId = 1;
function event<TPayload extends Record<string, unknown>>(
  episodeId: string,
  stepIdx: number,
  type: string,
  payload: TPayload
): ArcEvent<TPayload> {
  return {
    id: eventId++,
    episode_id: episodeId,
    step_idx: stepIdx,
    type,
    payload
  };
}

export const demoRuns: RunSummary[] = [
  {
    id: "demo-run",
    status: "running",
    created_at: "2026-07-07T10:00:00Z",
    metrics: {
      solve_rate: 0.73,
      ece: 0.11,
      overconf: 0.18,
      difficulty: 4.2
    }
  }
];

export const demoEpisodes: EpisodeSummary[] = [
  {
    id: "demo-episode-g03",
    run_id: "demo-run",
    game_id: demoGameSpec.id,
    idx: 18,
    result: "win",
    steps: 14,
    avg_conf: 0.77,
    overconf: 0.22,
    probe_steps: 2,
    revisions: 1,
    created_at: "2026-07-07T10:12:00Z"
  },
  {
    id: "demo-episode-g05",
    run_id: "demo-run",
    game_id: "g05_region",
    idx: 17,
    result: "win",
    steps: 22,
    avg_conf: 0.69,
    overconf: 0.16,
    probe_steps: 5,
    revisions: 2,
    created_at: "2026-07-07T10:10:00Z"
  },
  {
    id: "demo-episode-g04",
    run_id: "demo-run",
    game_id: "g04_diagonal",
    idx: 16,
    result: "timeout",
    steps: 100,
    avg_conf: 0.81,
    overconf: 0.37,
    probe_steps: 3,
    revisions: 0,
    created_at: "2026-07-07T10:08:00Z"
  }
];

export const demoEvents: ArcEvent[] = [
  event("demo-episode-g03", 0, "episode_start", {
    game_id: demoGameSpec.id,
    spec: demoGameSpec
  }),
  event("demo-episode-g03", 0, "observation", {
    grid: g0,
    step_idx: 0
  }),
  event("demo-episode-g03", 1, "hypotheses", {
    actions: [
      {
        action: "A1",
        items: [
          { math: "T(0,-1)", prob: 0.78 },
          { math: "M_h o T(0,-1) o M_h^-1", prob: 0.13 },
          { math: "I", prob: 0.04 }
        ]
      },
      {
        action: "A4",
        items: [
          { math: "T(1,0)", prob: 0.72 },
          { math: "R_1 o T(0,-1) o R_1^-1", prob: 0.16 },
          { math: "I", prob: 0.05 }
        ]
      }
    ]
  }),
  event("demo-episode-g03", 1, "plan", {
    intent: "goal",
    actions: ["A1", "A1", "A4"],
    imagined_grids: [g1Pred, withAgent(baseTiles, 2, 5), withAgent(baseTiles, 3, 5)],
    risk: 0.18
  }),
  event("demo-episode-g03", 1, "prediction", {
    action: "A1",
    predicted_grid: g1Pred,
    conf: 0.89
  }),
  event("demo-episode-g03", 1, "action_taken", {
    action: "A1",
    intent: "goal"
  }),
  event("demo-episode-g03", 1, "observation", {
    grid: g1Actual,
    step_idx: 1
  }),
  event("demo-episode-g03", 1, "outcome", {
    actual_grid: g1Actual,
    match_ratio: 0.84,
    surprise: 0.82,
    correct: false
  }),
  event("demo-episode-g03", 1, "belief_revision", {
    action: "A1",
    old_top: "T(0,-1)",
    new_candidates_count: 43,
    trigger: "collapse"
  }),
  event("demo-episode-g03", 2, "hypotheses", {
    actions: [
      {
        action: "A1",
        items: [
          { math: "M_h o T(0,-1) o M_h^-1", prob: 0.82 },
          { math: "T(0,+1)", prob: 0.12 },
          { math: "Conditional(wall,T(0,+1),I)", prob: 0.03 }
        ]
      },
      {
        action: "A4",
        items: [
          { math: "T(1,0)", prob: 0.7 },
          { math: "T(-1,0)", prob: 0.17 },
          { math: "I", prob: 0.04 }
        ]
      }
    ]
  }),
  event("demo-episode-g03", 2, "plan", {
    intent: "probe",
    actions: ["A2"],
    imagined_grids: [g2Pred],
    risk: 0.09
  }),
  event("demo-episode-g03", 2, "prediction", {
    action: "A2",
    predicted_grid: g2Pred,
    conf: 0.76
  }),
  event("demo-episode-g03", 2, "action_taken", {
    action: "A2",
    intent: "probe"
  }),
  event("demo-episode-g03", 2, "observation", {
    grid: g2Actual,
    step_idx: 2
  }),
  event("demo-episode-g03", 2, "outcome", {
    actual_grid: g2Actual,
    match_ratio: 1,
    surprise: 0.05,
    correct: true
  }),
  event("demo-episode-g03", 3, "hypotheses", {
    actions: [
      {
        action: "A1",
        items: [
          { math: "M_h o T(0,-1) o M_h^-1", prob: 0.86 },
          { math: "T(0,+1)", prob: 0.09 },
          { math: "I", prob: 0.02 }
        ]
      },
      {
        action: "A4",
        items: [
          { math: "T(1,0)", prob: 0.74 },
          { math: "T(-1,0)", prob: 0.13 },
          { math: "I", prob: 0.05 }
        ]
      }
    ]
  }),
  event("demo-episode-g03", 3, "plan", {
    intent: "goal",
    actions: ["A4", "A4", "A1"],
    imagined_grids: [g3Actual, g4Actual, withAgent(baseTiles, 4, 8)],
    risk: 0.12
  }),
  event("demo-episode-g03", 3, "prediction", {
    action: "A4",
    predicted_grid: g3Actual,
    conf: 0.81
  }),
  event("demo-episode-g03", 3, "action_taken", {
    action: "A4",
    intent: "goal"
  }),
  event("demo-episode-g03", 3, "observation", {
    grid: g3Actual,
    step_idx: 3
  }),
  event("demo-episode-g03", 3, "outcome", {
    actual_grid: g3Actual,
    match_ratio: 1,
    surprise: 0.02,
    correct: true
  }),
  event("demo-episode-g03", 4, "episode_end", {
    result: "win",
    steps: 14,
    avg_conf: 0.77,
    overconf: 0.22,
    probe_steps: 2,
    revisions: 1
  }),
  event("demo-episode-g03", 4, "generator_update", {
    arm: "conjugate_mirror+misleading_hint",
    reward: 0.62,
    ucb_scores: {
      "conjugate_mirror+misleading_hint": 1.22,
      "region_conditional+portal_swap": 0.96,
      "diagonal_compose": 0.84
    }
  })
];

export const demoMetrics: MetricPoint[] = Array.from({ length: 30 }, (_, idx) => ({
  episode_idx: idx + 1,
  solve_rate: 0.42 + Math.min(0.4, idx * 0.012),
  difficulty: 2.4 + idx * 0.07,
  ece: Math.max(0.08, 0.24 - idx * 0.004),
  overconf: Math.max(0.12, 0.36 - idx * 0.006),
  high_conf_error_rate: Math.max(0.04, 0.22 - idx * 0.004),
  median_steps: Math.max(13, 29 - idx * 0.35)
}));

export const demoCalibration: CalibrationData = {
  bins: [
    { mean_conf: 0.08, accuracy: 0.12, count: 14 },
    { mean_conf: 0.18, accuracy: 0.22, count: 19 },
    { mean_conf: 0.28, accuracy: 0.31, count: 21 },
    { mean_conf: 0.38, accuracy: 0.4, count: 28 },
    { mean_conf: 0.48, accuracy: 0.46, count: 34 },
    { mean_conf: 0.58, accuracy: 0.55, count: 37 },
    { mean_conf: 0.68, accuracy: 0.61, count: 33 },
    { mean_conf: 0.78, accuracy: 0.67, count: 27 },
    { mean_conf: 0.88, accuracy: 0.71, count: 18 },
    { mean_conf: 0.96, accuracy: 0.82, count: 9 }
  ],
  high_conf_errors: [
    {
      episode_id: "demo-episode-g03",
      step_idx: 1,
      conf: 0.89,
      math: "T(0,-1)",
      traps: ["conjugate_mirror", "misleading_hint"]
    }
  ]
};

export const demoTraps: TrapDatum[] = [
  {
    arm: "conjugate_mirror+misleading_hint",
    plays: 42,
    agent_win_rate: 0.58,
    overconf_mean: 0.28,
    ucb: 1.22
  },
  {
    arm: "region_conditional+portal_swap",
    plays: 27,
    agent_win_rate: 0.48,
    overconf_mean: 0.34,
    ucb: 0.96
  },
  {
    arm: "diagonal_compose",
    plays: 31,
    agent_win_rate: 0.71,
    overconf_mean: 0.17,
    ucb: 0.84
  },
  {
    arm: "permuted_buttons",
    plays: 53,
    agent_win_rate: 0.86,
    overconf_mean: 0.08,
    ucb: 0.42
  }
];

export function demoPreviewForEpisode(episode: EpisodeSummary) {
  return {
    episode,
    spec: demoGameSpec,
    grid: episode.id === "demo-episode-g03" ? g1Actual : g0,
    traps: demoGameSpec.meta?.traps ?? []
  };
}
