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
