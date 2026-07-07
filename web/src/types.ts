export type RunStatus =
  | 'queued'
  | 'starting'
  | 'running'
  | 'solved'
  | 'failed'
  | 'limit'
  | 'error'
  | 'completed'
  | 'stopped'

export interface GameInfo {
  game_id: string
  official_game_id: string
  title: string
  tags: string[]
  baseline_actions: number[]
  default_fps: number
  source: 'official' | 'synth-local' | 'demo'
}

export interface ActionCandidate {
  action: string
  action_id: number
  data: Record<string, number>
  score: number
  evidence: string
}

export interface FrameComponent {
  id: number
  color: number
  size: number
  center: { x: number; y: number }
  bounds: { x_min: number; y_min: number; x_max: number; y_max: number }
}

export interface ActionDetail {
  id: number
  name: string
  is_complex: boolean
  data_schema: Record<string, unknown>
}

export interface ChangedPixel {
  x: number
  y: number
  before: number
  after: number
}

export type TransformSpec =
  | { op: 'identity' }
  | { op: 'translate'; dx: number; dy: number }
  | { op: 'rotate'; k: number; pivot?: string }
  | { op: 'mirror'; axis: string }
  | { op: 'scale'; factor: number }
  | { op: 'color_map'; mapping: Record<string, number> }
  | { op: 'toggle'; cells: number[][]; color: number }
  | { op: 'compose'; fs: TransformSpec[] }
  | { op: 'conditional'; pred: Record<string, unknown>; if_true: TransformSpec; if_false: TransformSpec }
  | { op: 'periodic'; n: number; f: TransformSpec; g: TransformSpec }

export interface TransformHypothesis {
  hypothesis_id: string
  action_id: number
  scope: { object_selector: string; region: unknown | null }
  transform: TransformSpec
  readable: string
  support: number
  violations: number
  confidence: number
  complexity: number
  source: string
  alternatives: string[]
}

export interface ImaginationAudit {
  predicted_frame: number[][]
  plan_tree: Record<string, unknown>
  mode: 'exploit' | 'probe' | 'reset' | string
}

export interface SurpriseAudit {
  value: number
  pixel_error: number
  pixel_error_rate: number
  object_error: number
  belief_flips: Array<{ from: string; to: string }>
}

export interface CredibilityAudit {
  claimed: number
  calibrated: number
  gate: 'exploit' | 'probe' | string
}

export interface TraceStep {
  schema?: 'arc3-runner.audit.v2' | 'arc3-runner.audit.v3' | string
  index: number
  timestamp: string
  action_name: string
  action_id: number
  action_data: Record<string, number>
  frame: number[][]
  before_frame: number[][] | null
  raw_frame_layers: number[][][]
  state: string
  levels_completed: number
  win_levels: number
  available_actions: number[]
  available_action_details: ActionDetail[]
  observation_input: Record<string, unknown>
  perception: {
    width: number
    height: number
    background_color: number
    color_histogram: Array<{ color: number; count: number }>
    components: FrameComponent[]
  }
  changed_pixels: ChangedPixel[]
  observation: string
  detected_change: string
  hypothesis: string
  candidates: ActionCandidate[]
  agent_state_before: {
    step_index: number
    policy: string
    agent?: string
    action_stats: Record<string, { trials: number; cumulative_information_reward: number; mean_information_reward: number }>
    pending_click_candidates: Array<{ x: number; y: number }>
    used_clicks: Array<{ x: number; y: number }>
  }
  selected_reason: string
  action_request: Record<string, unknown>
  environment_response: Record<string, unknown>
  result: string
  changed_cells: number
  duration_ms: number
  audit_note: string
  hypotheses?: TransformHypothesis[]
  imagination?: ImaginationAudit
  surprise?: SurpriseAudit
  credibility?: CredibilityAudit
}

export interface GameRun {
  game_id: string
  official_game_id: string
  title: string
  tags: string[]
  baseline_actions: number[]
  default_fps: number
  status: RunStatus
  state: string
  levels_completed: number
  win_levels: number
  action_count: number
  started_at: string | null
  finished_at: string | null
  error: string | null
  steps: TraceStep[]
}

export interface SuiteRun {
  run_id: string
  status: RunStatus
  agent: string
  mode: 'official-live' | 'synth-local' | 'demo-replay'
  max_actions: number
  created_at: string
  started_at: string | null
  finished_at: string | null
  current_game_id: string
  game_order: string[]
  games: Record<string, GameRun>
  error?: string
}

// UI types for the refactored interface
export type AgentStrategyId = 'heuristic-explorer' | 'transform-aware' | 'action-sweep' | 'visual-click-scan'

export interface AgentStrategy {
  id: AgentStrategyId
  label: string
  description: string
  supportsComplexActions: boolean
}

export const AGENT_STRATEGIES: AgentStrategy[] = [
  { id: 'heuristic-explorer', label: 'Heuristic Explorer', description: '按未尝试优先和信息增益探索动作', supportsComplexActions: true },
  { id: 'transform-aware', label: 'Transform-Aware', description: '用变换假设做想象规划，并在低置信度时主动 probe', supportsComplexActions: false },
  { id: 'action-sweep', label: 'Action Sweep', description: '轮询未尝试的简单动作', supportsComplexActions: false },
  { id: 'visual-click-scan', label: 'Visual Click Scan', description: '按连通区域点击 complex action', supportsComplexActions: true },
]

export type InterfaceMode = 'visual' | 'data'

export type HistoryViewMode = 'gallery' | 'list' | 'timeline'

export interface TrainingStatus {
  status: 'idle' | 'running' | 'stopping' | 'completed' | 'error'
  current_generation: number
  total_generations: number
  current_game: string | null
  games_completed: number
  games_per_generation: number
  metrics: Record<string, number>
  error?: string
}

export interface TrainingGeneration {
  gen: number
  created_at: string
  agent_metrics: Record<string, number>
  gen_metrics: Record<string, unknown>
  weights: Record<string, number>
}

export interface SynthGameSummary {
  spec_id: string
  gen: number
  trap: string
  params: Record<string, unknown>
  fool_score: number
  solved: boolean
}

export interface TrainingKnowledge {
  priors: Array<{ action_key: string; family: string; support: number; total: number }>
  calibration: Array<{ bucket: number; claimed: number; hit_rate: number; n: number }>
  trap_signals: Array<{ trap: string; signature: string; hits: number }>
}

export interface SynthSpec {
  spec_id: string
  grid: number
  avatar: { color: number; start: [number, number] }
  goal: { type: string; target: [number, number]; color: number }
  rules: Record<string, TransformSpec>
  traps: Array<{ template: string; params: Record<string, unknown> }>
  max_steps: number
  win_levels: number
  title?: string
}
