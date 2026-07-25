export type Grid = number[][];

export type RunStatus = "running" | "paused" | "done" | string;

export interface RunSummary {
  id: string;
  config?: {
    episodes?: number;
    game_source?: string;
    seed?: number;
    [key: string]: unknown;
  };
  config_json?: string | Record<string, unknown>;
  status: RunStatus;
  created_at?: string;
  metrics?: Record<string, number>;
  latest_episodes?: EpisodeSummary[];
}

export interface EpisodeSummary {
  id: string;
  run_id: string;
  game_id: string;
  idx: number;
  result: "win" | "lose" | "timeout" | string;
  steps: number;
  avg_conf: number;
  overconf: number;
  probe_steps: number;
  revisions: number;
  created_at?: string;
}

export interface GameEntity {
  id: string;
  kind: string;
  x: number;
  y: number;
  color?: number;
}

export interface GameAction {
  program?: unknown;
  hint?: string;
}

export interface GameSpec {
  id: string;
  size: { w: number; h: number };
  tiles: Grid;
  entities?: GameEntity[];
  actions?: Record<string, GameAction>;
  regimes?: Array<{ actions: Record<string, GameAction> }>;
  win?: Record<string, unknown>;
  max_steps?: number;
  meta?: {
    traps?: string[];
    difficulty?: number;
    seed?: number;
    [key: string]: unknown;
  };
}

export type EventType =
  | "episode_start"
  | "observation"
  | "hypotheses"
  | "plan"
  | "prediction"
  | "action_taken"
  | "outcome"
  | "belief_revision"
  | "episode_end"
  | "generator_update"
  | string;

export interface ArcEvent<TPayload = Record<string, unknown>> {
  id?: number;
  episode_id: string;
  step_idx: number;
  type: EventType;
  payload: TPayload;
}

export interface EpisodeStartPayload {
  game_id: string;
  spec: GameSpec;
}

export interface ObservationPayload {
  grid: Grid;
  entities?: GameEntity[];
  state?: Record<string, unknown>;
  frames?: Grid[];
  raw?: Record<string, unknown>;
  official_state?: string;
  guid?: string;
  levels_completed?: number;
  win_levels?: number;
  available_actions?: Array<number | string>;
  step_idx?: number;
}

export interface HypothesisItem {
  program?: unknown;
  math: string;
  prob: number;
}

export interface ActionHypotheses {
  action: string;
  items: HypothesisItem[];
}

export interface HypothesesPayload {
  actions?: ActionHypotheses[];
  hypotheses?: ActionHypotheses[];
}

export interface PlanPayload {
  intent: "goal" | "probe" | string;
  actions: string[];
  imagined_grids: Grid[];
  risk: number;
}

export interface PredictionPayload {
  action: string;
  predicted_grid: Grid;
  conf: number;
  math?: string;
}

export interface ActionTakenPayload {
  action: string;
  intent: "goal" | "probe" | string;
}

export interface OutcomePayload {
  actual_grid: Grid;
  match_ratio: number;
  surprise: number;
  correct: boolean;
}

export interface BeliefRevisionPayload {
  action: string;
  old_top: string;
  new_top?: string;
  new_candidates_count: number;
  trigger: string;
}

export interface EpisodeEndPayload {
  result: string;
  steps: number;
  avg_conf: number;
  overconf: number;
  probe_steps: number;
  revisions: number;
}

export interface GeneratorUpdatePayload {
  arm: string;
  reward: number;
  ucb_scores: Record<string, number>;
}

export interface MetricPoint {
  run_id?: string;
  episode_idx: number;
  name?: string;
  value?: number;
  solve_rate?: number;
  difficulty?: number;
  ece?: number;
  overconf?: number;
  high_conf_error_rate?: number;
  median_steps?: number;
  [key: string]: string | number | undefined;
}

export interface CalibrationBin {
  mean_conf: number;
  accuracy: number;
  count: number;
}

export interface HighConfidenceError {
  episode_id: string;
  step_idx: number;
  conf: number;
  math?: string;
  traps?: string[];
}

export interface CalibrationData {
  bins: CalibrationBin[];
  high_conf_errors: HighConfidenceError[];
}

export interface TrapDatum {
  arm: string;
  plays: number;
  agent_win_rate: number;
  overconf_mean: number;
  ucb: number;
}

export interface EpisodePreview {
  episode: EpisodeSummary;
  spec?: GameSpec;
  grid?: Grid;
  traps: string[];
}
