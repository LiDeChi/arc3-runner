# ARC3 Runner

ARC3 Runner 是一个面向 ARC-AGI-3 的本地 Agent 运行与轨迹审计界面。它通过官方 `arc-agi` Toolkit 获取公开环境、执行动作，并把每局游戏的帧、关卡进度、候选动作、选择依据和环境结果组织成可回放的可视化工作台。

![ARC3 Runner 可视化游戏界面](artifacts/qa/visual-interface-desktop.png)

## 已实现

### 可视化游戏工作台

- **顶栏环境方块**：所有环境以紧凑方块排列在顶栏，用填充色和边框区分 idle、running、solved、failed 等状态。单击选择环境，勾选方块纳入运行，支持搜索过滤。
- **可视化游戏界面**：当前帧渲染（PixelGrid）+ 动作空间 + 候选动作评分 + 观察/变化/假设/执行结果，合并为一个整体面板。
- **一键数据界面**：同一帧可在"可视化"和"数据"模式间切换，数据视图使用紧凑 JSON 渲染，避免一行一个数字。
- **多视图历史帧序列**：支持画廊式（横向缩略卡片）、列表式（紧凑行表）、时间线式（拖动 + 详情栏）三种视图查看过去每一帧。
- **回放与重玩**：回放 = 播放已有轨迹；重玩 = 以选定策略重新执行环境，创建新 run_id。

### Agent、训练与运行

- 自动发现当前账号可访问的官方公开环境。
- 勾选一个或多个游戏并顺序运行 Agent。
- 支持策略选择（Heuristic Explorer / Transform-Aware / Action Sweep / Visual Click Scan）。
- Transform-Aware 使用动作变换假设做一步想象规划，按置信度在 exploit/probe 间切换，并把 plan tree、surprise、credibility 写入 audit.v3。
- 键盘动作优先覆盖未尝试动作，再按历史信息增益探索。
- 点击动作从视觉连通区域中心生成候选坐标。
- 每一步保存 64×64 合成帧、前后差异、可用动作、关卡进度和延迟。
- 保留 Agent 收到的原始帧图层、动作 Schema、颜色统计、全部连通区域和逐像素差异。
- 展示 Agent 的动作试验次数、信息增益统计、全部候选评分与点击探索队列。
- 展示实际 `EnvironmentWrapper.step()` 请求及官方环境响应，不隐藏中间操作。
- 支持播放、暂停、逐帧跳转、速度切换、时间线定位。
- 侧栏决策详情面板（可开关）：展示观察、帧变化、假设、候选动作、执行动作的审计流。
- API 不可用时自动保留离线演示回放，便于先检查界面。
- 训练模式包含 SynthFactory、训练总览、可信度、知识库四个页签。
- SynthFactory 支持生成 T1 规则突变和 T6 伪装偏移合成题，并可直接创建 `synth-local` run。
- 对抗训练循环在本地合成环境上运行 transform-aware agent，计算 solve_rate、prediction_accuracy、ECE、fool_score，并把世代、episode、先验、校准和陷阱信号写入 SQLite；后续合成 episode 会复用已学到的非 identity 动作先验与可信度校准。
- 每 5 个训练世代可触发官方公开环境对照评测，比较 Heuristic Explorer、原始 Transform-Aware、训练后 Transform-Aware 的 solve_rate、prediction_accuracy、ECE；官方评测只迁移校准策略，不把合成 action_id 先验直接套到官方环境。

审计内容是结构化运行摘要，不保存或展示模型隐藏思维链。

## 运行

需要 Python 3.12、`uv` 和 Node.js。

```bash
make install
make dev
```

默认地址：

- Web：<http://127.0.0.1:5173>（端口占用时 Vite 会自动选择下一个端口）
- API：<http://127.0.0.1:8010>
- API 文档：<http://127.0.0.1:8010/docs>

官方 Toolkit 会尝试获取匿名 API key。需要访问匿名范围之外的环境时，可设置：

```bash
export ARC_API_KEY="your_key"
```

## 验证

```bash
make test
make lint
make build
```

浏览器验收截图位于 `artifacts/qa/`，包括可视化界面、画廊历史、列表历史、数据界面、移动端布局。

## 术语说明

- **回放 (Replay)**：播放已存在的 `steps` 序列，不触发新的 API 调用。
- **重新回放 (Replay from Start)**：将 playhead 回到首帧并播放已有轨迹。
- **重玩 (Rerun)**：以选定策略重新执行环境，创建新的 `run_id`，不复用旧步骤。

## 主要接口

- `GET /api/games`：发现官方环境。
- `POST /api/runs`：启动一组游戏运行，支持 `agent` 策略参数。
- `GET /api/runs/{run_id}`：读取持续更新的完整运行详情。
- `GET /api/runs`：列出本进程中的运行。
- `GET /api/synth/specs` / `POST /api/synth/specs`：列出或生成合成 GameSpec。
- `GET /api/synth/specs/{spec_id}`：查看单个合成 GameSpec。
- `POST /api/training/start` / `POST /api/training/stop`：启动或停止对抗训练。
- `GET /api/training/status`：读取当前训练状态和实时指标。
- `GET /api/training/generations`：读取世代指标，包含官方对照评测报告（触发时）。
- `GET /api/training/generations/{gen}/games`：读取某代合成游戏画廊数据。
- `GET /api/training/episodes/{episode_id}`：读取训练 episode 摘要。
- `GET /api/training/knowledge`：读取动作先验、校准表和陷阱前兆库。

普通运行状态仍保存在内存中；训练知识库默认写入 `data/runner.db`。

## 项目结构

```
├── server/main.py        # FastAPI API、ARC 官方运行时、Agent 策略
├── server/transforms.py  # Transform DSL
├── server/hypothesis.py  # 假设拟合、想象审计、surprise
├── server/policy.py      # transform-aware / probe / exploit 策略
├── server/synth_env.py   # 本地合成环境
├── server/traps.py       # T1/T6 陷阱模板
├── server/store.py       # SQLite 训练持久化
├── server/trainer.py     # 对抗训练循环与官方评测 hook
├── web/src/
│   ├── App.tsx           # 顶层布局与状态
│   ├── api.ts            # API 调用
│   ├── demo.ts           # 离线演示数据
│   ├── types.ts          # 数据契约与 UI 类型
│   ├── styles.css        # 全局样式
│   └── components/
│       ├── EnvironmentStrip.tsx   # 顶栏环境方块条
│       ├── VisualGameInterface.tsx  # 可视化/数据游戏界面
│       ├── FrameHistory.tsx       # 历史帧序列（画廊/列表/时间线）
│       ├── CompactJson.tsx        # 紧凑 JSON/矩阵渲染
│       ├── PixelGrid.tsx          # 像素帧渲染
│       ├── TraceInspector.tsx     # 决策详情侧栏
│       ├── SynthFactory.tsx       # 合成游戏画廊与 GameSpec
│       ├── TrainingDashboard.tsx  # 训练总览与官方对照评测
│       ├── CalibrationView.tsx    # 可信度/校准图
│       ├── KnowledgeView.tsx      # 动作先验、校准表、陷阱信号
│       ├── HypothesisPanel.tsx    # 动作变换假设与向量场
│       ├── ImaginationView.tsx    # 想象帧/实际帧/惊奇规划树
│       ├── VectorFieldOverlay.tsx # 变换向量示意
│       └── EventDetail.tsx        # 旧详情面板（逻辑保留，UI 已融入新组件）
├── docs/doc.md           # 产品需求笔记
├── plans/                # 执行计划和交接文档
└── artifacts/qa/         # 验收截图
```
