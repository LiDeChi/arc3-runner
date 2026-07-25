# 可视化游戏界面与 Agent 重玩改造方案

## 目标

把当前 ARC3 Runner 从“侧栏选环境 + 中央帧 + 下方详情 tab + 右侧审计流”的布局，改成以“可视化游戏界面”为核心的游戏/审计工作台：

- 环境入口移到顶栏，用紧凑方块表示每个环境，并用填充、边框、描边和选中态区分状态。
- 游戏渲染图、action 空间、当前观察/决策所需信息合并成一个整体，命名为“可视化游戏界面”。
- 过去每一帧的可视化游戏界面和已执行操作，以可拖动的历史序列直接排列出来，不依赖点击后才展示。
- 历史序列支持画廊式、列表式、时间线式切换，支持回放、回到首帧重新回放、单步详情。
- 每帧“可视化游戏界面”和“数据界面”等价，同一帧可一键切换两种表示。
- JSON/数组/矩阵数据紧凑但清晰，避免默认 `JSON.stringify(value, null, 2)` 造成“一行一个数字”。
- 明确区分“回放已有轨迹”和“让 agent 按选定策略重新玩一遍”。

## 现状依据

需求来源：`docs/doc.md`。

当前代码入口和边界：

- `web/src/App.tsx`：全局状态、布局、运行启动、播放控制。
- `web/src/components/GameRail.tsx`：当前左侧环境列表，需要迁移为顶栏环境方块。
- `web/src/components/Timeline.tsx`：当前点状时间线，需要扩展为多视图历史序列。
- `web/src/components/EventDetail.tsx`：已有轨迹、完整输入、对象解析、决策状态、实际操作、帧差异、完整事件 tab，是数据界面改造的主要来源。
- `web/src/components/TraceInspector.tsx`：右侧决策审计流，后续应并入可视化游戏界面的当前帧详情，或降级为详情抽屉。
- `web/src/types.ts`：已有 `TraceStep` 数据足以构成视觉/数据等价界面，初版不需要改后端 schema。
- `server/main.py`：已有 `RunRequest.agent`，但前端 `createRun()` 目前硬编码 `Heuristic Explorer`，需要为策略/重玩留出参数。
- `web/src/demo.ts`：离线演示数据需要同步支持新 UI。

## 非目标

- 不实现持久化历史存储。当前 run 仍可保存在内存，除非后续另起计划。
- 不展示或推断模型隐藏思维链。继续只展示结构化审计摘要。
- 不大改 ARC 官方 Toolkit 调用方式。
- 不为了 UI 改造重写 agent 策略引擎。第一版只做必要策略接口和最小可运行策略分支。

## 建议数据与状态模型

前端新增局部 UI 状态：

```ts
type InterfaceMode = 'visual' | 'data'
type HistoryViewMode = 'gallery' | 'list' | 'timeline'
type AgentStrategyId = 'heuristic-explorer' | 'action-sweep' | 'visual-click-scan'
```

策略定义先放前端常量，后端只接收并记录：

```ts
interface AgentStrategy {
  id: AgentStrategyId
  label: string
  description: string
  supportsComplexActions: boolean
}
```

后端 `RunRequest` 可扩展：

```py
class RunRequest(BaseModel):
    game_ids: list[str] = Field(min_length=1, max_length=25)
    max_actions: int = Field(default=40, ge=1, le=80)
    agent: str = "heuristic-explorer"
```

第一版行为：

- `heuristic-explorer`：保留当前 `_choose_action()` 行为。
- `action-sweep`：对 simple action 做轮询/未尝试优先，不使用视觉点击候选。
- `visual-click-scan`：若存在 complex action，优先按连通区域中心点击；否则回退到 `heuristic-explorer`。

如果时间有限，只实现 UI 选择和后端记录，实际行为仍走当前策略；但界面文案必须标明当前只启用一个真实策略，避免伪装成已完成多策略。

## 实施顺序

### 1. 建立布局骨架

新增/重命名组件：

- `web/src/components/EnvironmentStrip.tsx`
- `web/src/components/VisualGameInterface.tsx`
- `web/src/components/FrameHistory.tsx`
- `web/src/components/CompactJson.tsx`
- 可选：`web/src/components/AgentControls.tsx`

在 `App.tsx` 中先完成布局重排：

- 顶栏保留 brand、session、连接态、agent 控制、启动按钮。
- 将环境选择从左侧 `GameRail` 改为顶栏中段横向/换行紧凑方块。
- 主工作区改为两段：
  - 上：`VisualGameInterface`，展示当前帧的视觉界面或等价数据界面。
  - 下：`FrameHistory`，展示历史帧序列与回放控制。
- 右侧 `TraceInspector` 暂时可以保留为详情栏，但不要让当前决策信息只存在右栏；当前帧关键观察、动作空间、候选动作、实际动作必须进入 `VisualGameInterface`。

验收：

- 环境列表不再占左侧整列。
- 小屏下环境方块可以横向滚动，不挤压启动控制。
- 当前选中环境、勾选环境、运行状态可从顶栏直接识别。

### 2. 顶栏环境方块

`EnvironmentStrip` 输入：

```ts
interface EnvironmentStripProps {
  games: GameInfo[]
  runs: Record<string, GameRun>
  selectedGameId: string
  checked: Set<string>
  query: string
  onQuery: (value: string) => void
  onSelect: (gameId: string) => void
  onToggle: (gameId: string) => void
}
```

状态视觉建议：

- idle：透明填充，细灰边。
- checked：红色外描边或左上角勾选点。
- queued/starting：虚线边或弱填充。
- running：实心高亮，轻微脉冲，但不要影响布局尺寸。
- solved：绿色填充或绿色底边。
- failed/error：红色边框，暗红填充。
- selected：双层边框或更亮文字。

交互：

- 单击方块：选择环境。
- 方块内小勾选区域或 modifier 点击：切换是否纳入下一次 run。
- hover title 显示 `game_id`、官方 ID、状态、action 数、关卡进度。
- 保留搜索入口，但可以做成顶栏小输入或折叠菜单。

验收：

- 不同状态只靠文字以外的填充/边缘也能区分。
- 25 个公开环境在 1440px 宽度下能完整或近完整显示；不足时横向滚动。

### 3. 可视化游戏界面

`VisualGameInterface` 职责：

- 当前帧渲染：复用 `PixelGrid`。
- 当前可用 action 空间：展示 `available_action_details`，用紧凑按钮/表格表示 action id、name、simple/complex、schema 摘要。
- 本步候选动作：展示 `candidates` 排名、分数、证据，并突出已选动作。
- 当前观察信息：展示 state、levels、changed cells、duration、observation、detected_change、hypothesis、selected_reason。
- 当前帧模式切换：`visual` / `data` 一键切换。

建议视觉布局：

- 左侧：大帧。
- 右侧上：状态指标和实际动作。
- 右侧中：action space 与候选动作。
- 右侧下：观察/变化/策略摘要。
- 数据模式：同一区域替换为结构化数据视图，不跳转到另一个 tab。

数据模式内容：

- `observation_input`
- `available_action_details`
- `agent_state_before`
- `action_request`
- `environment_response`
- `perception`
- `changed_pixels`
- `raw_frame_layers` 只显示摘要和可展开矩阵，避免默认展开所有数字。

验收：

- 在不打开下方历史详情的情况下，用户能看到“这一帧 agent 看到了什么、能做什么、选了什么、为什么选、环境返回了什么”。
- `visual` 和 `data` 切换不改变选中的 frame index。
- 当前帧详情不依赖右侧 `TraceInspector` 才能理解。

### 4. 紧凑 JSON/矩阵渲染

新增 `CompactJson`，替换 `EventDetail` 里直接 `JSON.stringify(value, null, 2)` 的主要位置。

渲染规则：

- primitive array 长度不大时单行显示：`[0, 1, 2, 3]`。
- 数字矩阵按行显示，每行压缩成 `[0,0,1,1,0...]`，不要每个数字一行。
- object 用 key/value 行；值是简单对象时内联，复杂对象可缩进一级。
- 大数组默认显示前 N 项和总数，提供“展开全部”。
- `raw_frame_layers` 和 `frame` 这类二维/三维数组默认摘要，允许按层展开。

验收：

- `raw` 或数据模式里不再出现大面积一列数字。
- action schema、请求/响应 JSON 能快速扫读。
- 长数据不会撑破布局，横向和纵向滚动在组件内部完成。

### 5. 历史帧序列与多视图

新增 `FrameHistory`，替代或包裹当前 `Timeline`。

三种视图：

- `gallery`：横向卡片，每张卡展示缩略 `PixelGrid`、step、action、结果/进度、changed cells。
- `list`：高密度行表，适合快速扫动作和结果。
- `timeline`：保留时间轴概念，但要能拖动/横向滚动，并显示关键 step 标记。

共同功能：

- 始终排列展示过去每一帧，不要求点开后才看到。
- 单击任意历史项选中该 step。
- 回放：按当前 `speed` 移动 playhead。
- 重新回放：playhead 回到 0 并开始播放已有轨迹。
- 每一步详情：可用内联展开、详情抽屉或把 `VisualGameInterface` 切到该 step。

命名边界：

- “回放”：播放已有 `steps`。
- “重新回放”：从 step 0 重新播放已有 `steps`。
- “重玩”：新建一次 run，让 agent 以选定策略重新执行环境。

验收：

- 用户打开页面后不用点击 timeline 点，也能横向看到历史帧。
- 画廊/列表/时间线切换保留当前 step。
- “重新回放”和“重玩”在按钮文案、位置、行为上不混淆。

### 6. Agent 策略、启动与重玩

前端：

- 把 `agent` 从硬编码改为可选策略。
- `createRun(gameIds, maxActions, strategyId)`。
- 顶栏或 `AgentControls` 展示策略选择、max actions、启动按钮。
- 针对当前环境提供“重玩本环境”；针对勾选环境提供“运行勾选”。
- 对已有 run 提供“按当前策略重玩”，实际行为是新建 run，不覆盖旧 run。

后端：

- `RunRequest.agent` 接收策略 id。
- `run["agent"]` 记录策略 id 或 label。
- 可选：按策略分支 `_choose_action()`；如果只做最小版本，必须在 README/界面说明只有 `heuristic-explorer` 是真实策略。

验收：

- 启动新 run 时 payload 包含选择的策略。
- 新 run 的 `agent` 字段和 UI 显示一致。
- 点击“重玩”会创建新的 run_id，并从 step 0 开始重新执行，不复用旧 steps。

### 7. 样式与响应式

重点修改 `web/src/styles.css`：

- 顶栏高度可以从 58px 调整到 64-76px，但不要让主视图过窄。
- 环境 strip 用固定尺寸方块，例如 26-32px。
- `VisualGameInterface` 用稳定 grid track，避免 JSON 或长 action 名撑布局。
- 历史画廊卡片固定宽高，缩略帧固定 aspect-ratio。
- 移动端：顶栏环境 strip 横向滚动；主界面上下排列；历史序列优先画廊或列表。

验收：

- 桌面 1440×900、窄屏 1024×768、移动宽 390 下无明显文本重叠。
- 任何按钮 hover/active 不改变控件尺寸。

## 文件级任务清单

1. `web/src/types.ts`
   - 增加 UI 使用的策略/视图类型，或在组件内局部定义。
   - 如后端返回 `agent` 保持 string，则不强制改 `SuiteRun`。

2. `web/src/api.ts`
   - `createRun(gameIds, maxActions, agent)`。
   - 保持向后兼容默认策略。

3. `server/main.py`
   - 确认 `RunRequest.agent` 接收策略 id。
   - 可选实现策略分支；至少保证记录和返回。

4. `web/src/components/EnvironmentStrip.tsx`
   - 从 `GameRail` 提取状态映射和选择/勾选交互。
   - 用方块 UI 替代大行列表。

5. `web/src/components/VisualGameInterface.tsx`
   - 汇总当前 frame、action space、候选动作、观察/决策/响应摘要。
   - 包含 `visual` / `data` 切换。

6. `web/src/components/CompactJson.tsx`
   - 实现紧凑 JSON、数组、矩阵渲染。
   - 替换 `EventDetail` 和新数据界面里的大 JSON。

7. `web/src/components/FrameHistory.tsx`
   - 实现 `gallery` / `list` / `timeline` 三视图。
   - 实现播放、重新回放、速度、step 选择。

8. `web/src/App.tsx`
   - 迁移布局与状态。
   - 删除或停止使用 `GameRail`。
   - 明确 replay/rerun 行为。

9. `web/src/demo.ts`
   - 确认 demo steps 足够展示画廊、列表、数据模式和重玩入口。

10. `web/src/styles.css`
    - 完成新布局、状态方块、历史卡片、紧凑数据视图、响应式。

11. `README.md`
    - 更新已实现/运行说明中关于界面的描述。
    - 说明回放 vs 重玩的区别。

## 验证步骤

基础验证：

```bash
make test
make lint
make build
```

人工验收：

```bash
make dev
```

在浏览器检查：

- 顶栏环境方块能选择、勾选、显示状态。
- 运行勾选环境能启动官方 run；API 不可用时仍能看 demo。
- 当前帧可在“可视化游戏界面”和“数据界面”一键切换。
- 历史帧画廊、列表、时间线都能切换并选择 step。
- 回放、重新回放只移动已有 steps。
- 重玩会创建新的 run_id。
- JSON/矩阵数据没有一行一个数字的大面积展开。

建议截图：

- `artifacts/qa/visual-interface-desktop.png`
- `artifacts/qa/frame-history-gallery.png`
- `artifacts/qa/frame-history-list.png`
- `artifacts/qa/data-interface-compact-json.png`
- `artifacts/qa/mobile-layout.png`

## 给下一个模型的执行提示

请先读：

1. `AGENTS.md`
2. `README.md`
3. `docs/doc.md`
4. 本文件
5. `web/src/App.tsx`
6. `web/src/components/EventDetail.tsx`
7. `web/src/components/Timeline.tsx`
8. `server/main.py`

执行策略：

- 先做前端布局和组件拆分，再做后端策略记录。
- 保持 `TraceStep` 数据契约稳定，除非确实必须改。
- 优先让 demo mode 完整可用，再验证 official-live。
- 每完成一个阶段运行 `cd web && npm run build`，最后运行完整 `make test && make lint && make build`。
- 不要引入新的 UI 框架；继续用 React、CSS、lucide-react。
- 不要把“回放”和“重玩”混成一个按钮。
- 不要恢复左侧大环境列表，环境入口必须在顶栏方块化。

## 风险与处理

- 策略行为可能变成“只显示未真正切换”。处理：第一版如果不实现多策略分支，界面只显示一个可用策略，其他策略不要做成可选。
- 历史帧数量变多会影响 DOM 性能。处理：初版先限制缩略卡片内容；如果超过 200 step，再做虚拟列表。
- JSON 数据过大。处理：`CompactJson` 默认折叠大数组/矩阵。
- 顶栏空间不足。处理：环境 strip 横向滚动，控制区固定在右侧。

## 完成定义

这项改造完成时，应满足：

- 用户可以在顶栏看见并切换所有环境。
- 用户可以把某一帧作为“游戏界面”看，也可以一键切到等价“数据界面”看。
- 用户可以直接拖动/浏览过去每一帧，不需要先点 timeline 才看到历史。
- 用户能清楚地区分已有轨迹回放和 agent 重新玩一局。
- 后续模型能依据本计划继续实现，而不需要重新解释需求。
