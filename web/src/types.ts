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
  source: 'official' | 'demo'
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

export type TransformSpec = {
  op: string
  [key: string]: unknown
}

export interface TransformHypothesis {
  action: string
  action_id: number
  transform: TransformSpec
  readable?: string
  confidence: number
  calibrated_confidence?: number
  support?: number
  total?: number
  target?: string
  alternatives?: Array<{
    transform: TransformSpec
    readable?: string
    confidence: number
    support?: number
  }>
}

export interface SurpriseSignal {
  value: number
  predicted_error_pixels?: number
  belief_flips?: string[]
}

export interface CredibilitySignal {
  claimed: number
  calibrated: number
}

export interface ImaginationTrace {
  before_frame?: number[][] | null
  predicted_frame?: number[][] | null
  actual_frame?: number[][] | null
  error_pixels?: ChangedPixel[]
}

export interface TraceStep {
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
  decision_gate?: 'reset' | 'probe' | 'exploit'
  hypotheses?: TransformHypothesis[]
  surprise?: SurpriseSignal
  credibility?: CredibilitySignal
  imagination?: ImaginationTrace
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
  mode: 'official-live' | 'demo-replay'
  max_actions: number
  created_at: string
  started_at: string | null
  finished_at: string | null
  current_game_id: string
  game_order: string[]
  games: Record<string, GameRun>
  error?: string
}

export interface TrainingStartParams {
  generations: number
  games_per_gen: number
  trap_filter: string[]
}

export interface TrainingGenerationMetrics {
  gen: number
  solve_rate: number
  prediction_accuracy: number
  ece: number
  fool_score: number
  weights: Record<string, number>
}

export interface TrainingEpisodeSummary {
  episode_id: string
  gen: number
  game: string
  source: string
  trap: string
  solved: boolean
  fool_score: number
  steps: number
  max_surprise: number
  prediction_accuracy: number
  ece: number
}

export type TrainingEpisodeStep = TraceStep & {
  predicted_frame?: number[][]
}

export interface TrainingEpisodeDetail {
  episode_id: string
  gen: number
  spec_id: string
  game: string
  trap: string
  source: string
  solved: boolean
  fool_score: number
  metrics: TrainingEpisodeSummary
  steps: TrainingEpisodeStep[]
}

export interface KnowledgePrior {
  action: string
  action_id: number
  family: TransformSpec
  readable: string
  support: number
  total: number
}

export interface ReliabilityPoint {
  claimed: number
  hit_rate: number
  n: number
}

export interface TrainingKnowledge {
  priors: KnowledgePrior[]
  reliability: ReliabilityPoint[]
  surprise_timeline: Array<{
    gen: number
    episode_id: string
    step: number
    surprise: number
  }>
}

// --- UI state types for visual-game interface ---

export type InterfaceMode = 'visual' | 'data'
export type HistoryViewMode = 'gallery' | 'list' | 'timeline'
export type AgentStrategyId = 'transform-aware' | 'heuristic-explorer' | 'action-sweep' | 'visual-click-scan'

export interface AgentStrategy {
  id: AgentStrategyId
  label: string
  description: string
  supportsComplexActions: boolean
}

export const AGENT_STRATEGIES: AgentStrategy[] = [
  {
    id: 'transform-aware',
    label: 'Transform-Aware',
    description: '默认策略：显示逐动作空间变换假设、想象帧、惊奇与可信度审计。',
    supportsComplexActions: true,
  },
  {
    id: 'heuristic-explorer',
    label: 'Heuristic Explorer',
    description: '默认策略：优先未尝试动作，再按信息增益探索。',
    supportsComplexActions: true,
  },
  {
    id: 'action-sweep',
    label: 'Action Sweep',
    description: '对简单动作做轮询/未尝试优先，不使用视觉点击。',
    supportsComplexActions: false,
  },
  {
    id: 'visual-click-scan',
    label: 'Visual Click Scan',
    description: '若存在复杂动作，优先按连通区域中心点击；否则回退 Heuristic Explorer。⚠️ 仅供展示，未实现。',
    supportsComplexActions: true,
  },
]
