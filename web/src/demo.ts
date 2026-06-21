import type { ActionCandidate, GameInfo, GameRun, SuiteRun, TraceStep } from './types'

const publicGames = [
  ['ar25', 'keyboard_click'], ['bp35', 'keyboard_click'], ['cd82', 'keyboard_click'],
  ['cn04', 'keyboard_click'], ['dc22', 'keyboard_click'], ['ft09', 'logic'],
  ['g50t', 'keyboard'], ['ka59', 'keyboard_click'], ['lf52', 'click'],
  ['lp85', 'click'], ['ls20', 'keyboard'], ['m0r0', 'keyboard_click'],
  ['r11l', 'click'], ['re86', 'keyboard_click'], ['s5i5', 'click'],
  ['sb26', 'keyboard_click'], ['sc25', 'keyboard_click'], ['sk48', 'keyboard_click'],
  ['sp80', 'keyboard_click'], ['su15', 'click'], ['tn36', 'click'],
  ['tr87', 'keyboard'], ['tu93', 'keyboard_click'], ['vc33', 'click'],
  ['wa30', 'keyboard'],
] as const

export const demoGames: GameInfo[] = publicGames.map(([gameId, tag], index) => ({
  game_id: gameId,
  official_game_id: `${gameId}-demo${index.toString().padStart(4, '0')}`,
  title: gameId.toUpperCase(),
  tags: tag === 'logic' ? [] : [tag],
  baseline_actions: [22 + index, 41 + index * 2, 73 + index * 3],
  default_fps: 5,
  source: 'demo',
}))

const actionSequence = ['RESET', 'ACTION1', 'ACTION4', 'ACTION1', 'ACTION3', 'ACTION2', 'ACTION4', 'ACTION1', 'ACTION1', 'ACTION3', 'ACTION2', 'ACTION4', 'ACTION1', 'ACTION2', 'ACTION4', 'ACTION1']

function seededValue(x: number, y: number, step: number, seed: number): number {
  const wall = x === 0 || y === 0 || x === 31 || y === 31
  if (wall) return 5
  if ((x + seed) % 9 === 0 && y > 5 && y < 27) return 1
  if ((y + seed) % 11 === 0 && x > 3 && x < 29) return 1
  if ((x - 6) ** 2 + (y - 7) ** 2 < 7) return 3
  if ((x - 24) ** 2 + (y - 23) ** 2 < 10) return 8
  const px = 5 + ((step * 2 + seed) % 20)
  const py = 24 - ((step + seed) % 15)
  if (Math.abs(x - px) <= 1 && Math.abs(y - py) <= 1) return 9
  if (x === 27 && y >= 4 && y <= 7) return 10
  return 0
}

function buildFrame(step: number, seed: number): number[][] {
  return Array.from({ length: 32 }, (_, y) =>
    Array.from({ length: 32 }, (_, x) => seededValue(x, y, step, seed)),
  )
}

function candidates(step: number): ActionCandidate[] {
  return [1, 2, 3, 4].map((id) => ({
    action: `ACTION${id}`,
    action_id: id,
    data: {},
    score: Number((1.2 + ((step + id * 3) % 7) / 5).toFixed(3)),
    evidence: step < id ? '未尝试' : `平均信息增益 ${(0.4 + ((step + id) % 5) / 3).toFixed(2)}`,
  })).sort((a, b) => b.score - a.score)
}

export function buildDemoGameRun(gameId: string): GameRun {
  const seed = gameId.split('').reduce((sum, char) => sum + char.charCodeAt(0), 0) % 17
  const steps: TraceStep[] = actionSequence.map((actionName, index) => {
    const frame = buildFrame(index, seed)
    const beforeFrame = index > 0 ? buildFrame(index - 1, seed) : null
    const changedPixels = beforeFrame
      ? frame.flatMap((row, y) => row.flatMap((value, x) => beforeFrame[y][x] === value ? [] : [{ x, y, before: beforeFrame[y][x], after: value }]))
      : []
    const changed = changedPixels.length
    const level = index >= 14 ? 2 : index >= 8 ? 1 : 0
    const stepCandidates = index === 0 ? [] : candidates(index)
    const components = [
      { id: 0, color: 1, size: 92, center: { x: 15, y: 15 }, bounds: { x_min: 6, y_min: 7, x_max: 26, y_max: 24 } },
      { id: 1, color: 9, size: 9, center: { x: 5 + ((index * 2 + seed) % 20), y: 24 - ((index + seed) % 15) }, bounds: { x_min: 4, y_min: 9, x_max: 26, y_max: 25 } },
      { id: 2, color: 10, size: 4, center: { x: 27, y: 5 }, bounds: { x_min: 27, y_min: 4, x_max: 27, y_max: 7 } },
    ]
    const actionId = actionName === 'RESET' ? 0 : Number(actionName.replace('ACTION', ''))
    const reasoning = {
      schema: 'arc3-runner.audit.v2',
      observation: '读取当前像素帧与动作空间。',
      hypothesis: '优先测试未覆盖动作并保留信息增益。',
      candidates: stepCandidates,
      selected: { action: actionName, data: {}, reason: '选择当前最高评分动作。' },
    }
    return {
      index,
      timestamp: new Date(Date.now() - (actionSequence.length - index) * 860).toISOString(),
      action_name: actionName,
      action_id: actionId,
      action_data: {},
      frame,
      before_frame: beforeFrame,
      raw_frame_layers: [frame],
      state: index === actionSequence.length - 1 ? 'NOT_FINISHED' : 'NOT_FINISHED',
      levels_completed: level,
      win_levels: 7,
      available_actions: [1, 2, 3, 4],
      available_action_details: [1, 2, 3, 4].map((id) => ({ id, name: `ACTION${id}`, is_complex: false, data_schema: {} })),
      observation_input: {
        game_id: `${gameId}-demo-replay`, guid: 'demo-guid', state: 'NOT_FINISHED',
        levels_completed: level, win_levels: 7, full_reset: index === 0,
        available_actions: [1, 2, 3, 4], frame_layer_count: 1, frame_shapes: [[32, 32]],
        frame_layers_ref: 'raw_frame_layers',
      },
      perception: {
        width: 32,
        height: 32,
        background_color: 0,
        color_histogram: [
          { color: 0, count: 782 }, { color: 1, count: 92 }, { color: 5, count: 124 },
          { color: 9, count: 9 }, { color: 10, count: 4 },
        ],
        components,
      },
      changed_pixels: changedPixels,
      observation: `读取 32×32 帧；6 种颜色；检测到玩家、边界、两个稳定区域和一个目标形态。`,
      detected_change: index === 0 ? '首帧，无前序差异。' : `相对上一步有 ${changed} 个像素变化，主体向目标方向位移。`,
      hypothesis: level > 0
        ? '上一组动作触发关卡进展，优先复用有效方向并检测规则是否保持。'
        : '测试四个方向动作，保留能改变主体位置且不会回退的动作。',
      candidates: stepCandidates,
      agent_state_before: {
        step_index: index,
        policy: 'untried-first + information-gain; visual-component centers for ACTION6',
        action_stats: Object.fromEntries([1, 2, 3, 4].map((id) => [`ACTION${id}`, {
          trials: Math.floor(index / 4) + (index % 4 >= id ? 1 : 0),
          cumulative_information_reward: Number((index * id * 0.37).toFixed(4)),
          mean_information_reward: Number((id * 0.41).toFixed(4)),
        }])),
        pending_click_candidates: [],
        used_clicks: [],
      },
      selected_reason: index === 0
        ? '初始化环境并读取首帧。'
        : '选择当前信息增益最高、且未导致状态回退的方向动作。',
      action_request: {
        transport: index === 0 ? 'arcade.make' : 'EnvironmentWrapper.step',
        action: { id: actionId, name: actionName }, data: {}, reasoning,
      },
      environment_response: {
        game_id: `${gameId}-demo-replay`, guid: 'demo-guid', state: 'NOT_FINISHED',
        levels_completed: level, win_levels: 7, full_reset: index === 0,
        available_actions: [1, 2, 3, 4],
        action_input: { id: actionId, name: actionName, data: {}, reasoning },
        frame_layer_count: 1, frame_shapes: [[32, 32]], frame_layers_ref: 'raw_frame_layers',
      },
      result: `环境返回 NOT_FINISHED；关卡进度 ${level}/7；变化 ${changed} 格。`,
      changed_cells: changed,
      duration_ms: index === 0 ? 0 : 132 + ((index * 47 + seed) % 220),
      audit_note: '结构化审计摘要，不包含模型隐藏思维链。',
    }
  })

  return {
    game_id: gameId,
    official_game_id: `${gameId}-demo-replay`,
    title: gameId.toUpperCase(),
    tags: demoGames.find((game) => game.game_id === gameId)?.tags ?? [],
    baseline_actions: demoGames.find((game) => game.game_id === gameId)?.baseline_actions ?? [],
    default_fps: 5,
    status: gameId === 'ft09' ? 'solved' : gameId === 'vc33' ? 'failed' : 'running',
    state: 'NOT_FINISHED',
    levels_completed: gameId === 'ft09' ? 6 : 2,
    win_levels: 7,
    action_count: steps.length - 1,
    started_at: steps[0].timestamp,
    finished_at: null,
    error: null,
    steps,
  }
}

export function buildDemoSuite(): SuiteRun {
  const gameIds = ['ls20', 'ft09', 'vc33']
  return {
    run_id: 'demo-7f3a91',
    status: 'running',
    agent: 'Heuristic Explorer',
    mode: 'demo-replay',
    max_actions: 40,
    created_at: new Date(Date.now() - 18_000).toISOString(),
    started_at: new Date(Date.now() - 17_500).toISOString(),
    finished_at: null,
    current_game_id: 'ls20',
    game_order: gameIds,
    games: Object.fromEntries(gameIds.map((id) => [id, buildDemoGameRun(id)])),
  }
}
