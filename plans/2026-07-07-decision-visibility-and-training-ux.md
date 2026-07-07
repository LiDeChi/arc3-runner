# 决策可见性 + 训练模式可用性改造（Codex 执行计划）

## 背景与问题（用户反馈，2026-07-07）

1. 界面 UI 没做好，而且**看不懂怎么使用**。
2. **看不到 agent 的决策**，函数式的空间变形（`ACTION1 ≙ T(0,-1)` 这类假设）也看不到。

## 根因诊断（源码证据，务必先读这些位置）

后端 audit.v3 数据是齐的，问题几乎全在前端呈现层：

- **R1 `EventDetail.tsx` 没有被挂载**。`web/src/App.tsx` 已不再 import/渲染 `EventDetail`，而"假设"页签（`HypothesisPanel.tsx`，含逐动作变换函数表 + `VectorFieldOverlay` 向量示意）和"想象"页签（`ImaginationView.tsx`，含 BEFORE/IMAGINED/ACTUAL 三联图 + 误差高亮）都只挂在 `EventDetail` 里（`web/src/components/EventDetail.tsx:50-51,151-153`）。**组件写好了，用户根本到不了。**
- **R2 运行模式里决策信息只剩三行小字**。`VisualGameInterface.tsx:87-97,152-154` 只显示 top-1 假设的一行文本、surprise 一行、credibility 一行；完整的逐动作假设表、备选假设、规划树、想象帧都藏在"数据"模式的原始 JSON DataBlock 里（第 163-165 行），普通人读不了。
- **R3 训练 episodes 前端完全不可见**。`grep -rn "training/episodes" web/src` 为空——训练循环每一步的假设/惊奇/可信度都存进了 SQLite（`server/store.py` episodes 表），后端也有 `GET /api/training/episodes/{episode_id}`（`server/main.py:1110`），但前端没有任何页面读它。**训练过程是黑盒**，只能看到汇总数字。
- **R4 训练 episode 步骤没存帧**。`server/trainer.py:244-254` 的 steps 只存 action/reason/state/surprise/credibility/hypotheses，没有 before/after 帧——即使前端做了回放也画不出画面。
- **R5 Dashboard 不可操作、无解释**。`TrainingDashboard.tsx:37` 的按钮写死"开始 3×4"（3 代 × 4 局，用户无从知道含义、不能调参数）；指标条 `TrendRows` 用 div 高度画，`fool_score`（值域 3~5+）`value*100` 后全部顶满 100% 封顶（第 118 行），曲线失真；所有指标无中文解释、无空状态引导。
- **R6 校准页缺参照系**。`CalibrationView.tsx` 的 reliability 图没有"对角线=完美校准"参照，没有惊奇时间线，没有方案 4.3 设计的逐动作置信度曲线。
- **R7 `VectorFieldOverlay` 只支持 translate**（rotate/mirror/compose 不画），且没有任何地方能在真实帧上叠加向量场。
- **R8 全程无使用引导**。没有任何页面说明"先做什么、再看什么"。

## 目标

改完后用户能：
1. 打开任意一局（官方或合成），**一眼看到**每个动作当前的假设函数（数学串 + 置信度条 + 向量示意）、本步为什么选这个动作（probe/exploit + 理由）、想象帧 vs 实际帧的差异。
2. 在训练模式**下钻到任意世代 → 任意 episode → 任意一步**，看到该步的假设、惊奇、可信度和帧画面。
3. 不看文档也能明白每个按钮/指标是什么（内联帮助 + 空状态引导）。

## 约束

- 不改数据契约的语义，只允许**新增**字段（audit.v3 兼容）。
- 复用现有组件与 CSS 模式（styles.css 的 vgi-*/fh-*/training-* 体系），不引入新框架/图表库；折线图用手写 SVG。
- 每个任务完成后 `make test && make lint && make build` 必须全绿。
- 中文 UI 文案，与现有风格一致。

---

## WS-A 决策可见性（最高优先级，先做）

### A1. 把决策面板做进运行模式主界面

**文件**：`web/src/App.tsx`、`web/src/components/EventDetail.tsx`

把 `EventDetail`（九页签：轨迹/完整输入/对象解析/决策状态/实际操作/帧差异/完整事件/假设/想象）重新挂载回 App 运行模式：位置在 `VisualGameInterface` 之下、`FrameHistory` 之上，默认**折叠为一条页签栏**，点击任一页签展开（记住上次选择，`useState<DetailTab | null>`）。`EventDetail` 已接收 `tab`/`onTab` props，App 需补状态。

**验收**：运行任意 demo/官方局，能点开"假设"页签看到逐动作变换函数表，点开"想象"页签看到三联图。

### A2. VGI 可视化侧栏的"假设"面板升级为决策卡

**文件**：`web/src/components/VisualGameInterface.tsx`、`web/src/styles.css`

把现在 87-97 行的三行小字换成一块"决策卡"（放在侧栏最顶部，替换旧的 observation/hypothesis 文本面板位置）：

```
┌ 本步决策 ────────────────────────────────┐
│ [EXPLOIT] 选择 ACTION1                    │ ← gate 徽章：exploit 绿 / probe 黄
│ ACTION1 ≙ T(0,-1) on foreground          │ ← 等宽字体大号数学串
│ 置信 ████████░░ 87% (校准后 79%)          │ ← 双色条：claimed 淡色，calibrated 实色
│ 惊奇 0.05 · 3 px 预测误差                 │ ← surprise>0.3 时整行变红并加 ⚠
│ 理由：Transform-Aware exploit: …          │ ← step.selected_reason
└──────────────────────────────────────────┘
```

下面紧跟一张紧凑表"全部动作假设"（每行：ACTIONn / 数学串 / conf% / support），数据来自 `step.hypotheses`，行内 hover 显示 alternatives。

**验收**：可视化模式不切换页签就能看到选中动作的函数假设与全部动作的假设一览。

### A3. 想象三联图快捷入口

**文件**：`web/src/components/VisualGameInterface.tsx`

主帧区角落加一个"想象对比"切换（图标按钮）。开启后主帧区变成 `ImaginationView` 同款三联图（直接复用该组件或抽出共享子组件），关闭恢复单帧。默认关闭；当 `step.surprise.value >= 0.3` 时按钮上加红点提示"这一步预测失误，值得看"。

**验收**：点开后能看到 BEFORE/IMAGINED/ACTUAL 三帧和误差高亮；有惊奇的步骤按钮带红点。

### A4. 惊奇时间线

**文件**：`web/src/components/FrameHistory.tsx`、`web/src/styles.css`

- timeline 视图：每个 tick 按 `step.surprise?.value` 着色（0=默认色 → 1=红），有 `belief_flips` 的步骤 tick 上方加 ⚡ 角标。
- gallery 卡片：`fh-card-info` 里加 surprise 徽章（>0.3 红底）。
- list 视图：加 "surprise" 一列。

**验收**：跑一局 T1/T6 合成题，时间线上能一眼找到规则突变发生的那一步（红 tick + ⚡）。

### A5. VectorFieldOverlay 支持 rotate / mirror / compose

**文件**：`web/src/components/VectorFieldOverlay.tsx`

- `translate`：保持箭头（现状）。
- `rotate`：画弧线箭头（SVG path，k 决定弧度方向与 90k° 标注）。
- `mirror`：画对称轴虚线 + 双向箭头。
- `compose`：横排子变换小图标序列，中间 "∘"。
- `periodic`：`[f]×n → g` 两个子图标加箭头。
- 其他 op（toggle/color_map/conditional/identity）：显示文字缩写徽章（G/C/if/I）。

**验收**：`web/src/demo.ts` 的演示数据中加入 rotate 与 compose 假设各一条，假设表 VECTOR 列能正确画出。

---

## WS-B 训练模式可用性

### B1. 训练参数表单 + 指标解释 + 空状态引导

**文件**：`web/src/components/TrainingDashboard.tsx`、`web/src/api.ts`、`web/src/styles.css`

- 把"开始 3×4"换成表单：世代数（默认 10）、每代局数（默认 12）、陷阱类型多选（T1/T6，默认全选），点"开始训练"调 `startTraining(params)`（`api.ts` 的 `startTraining` 需支持参数透传到 `POST /api/training/start` 的 body，后端已支持 `generations/games_per_gen/trap_filter`，核对 `server/main.py:1077` 的 request model 字段名）。
- 每个指标标签旁加 `title` tooltip（悬浮中文解释）：
  - 通关率：本代合成题的解出比例。
  - 预测精确度：想象帧与实际帧的平均一致度（1-平均惊奇）。
  - ECE：校准误差——agent"声称多有把握"与"实际多准"的差距，越低越好。
  - fool_score：合成器骗分——骗到高置信预测才得分，越低说明 agent 越难骗。
- 无世代数据时显示引导卡（替代现在的一句话）：三步说明"1 设参数 → 2 开始训练 → 3 点任意世代下钻查看 agent 每一步决策"。

**验收**：不看文档能配置并启动一次训练；每个指标悬浮有解释。

### B2. 世代 → episode → 单步 下钻（打开训练黑盒，本工作流核心）

**文件**：后端 `server/trainer.py`、`server/main.py`；前端 `web/src/api.ts`、`web/src/types.ts`、`web/src/components/TrainingDashboard.tsx`、新建 `web/src/components/EpisodeReplay.tsx`

后端（先做）：
1. `trainer.py` `run_training_episode` 的 steps 里**补存帧**：每步加 `"before_frame": frame, "frame": next_frame, "predicted_frame": audit["imagination"]["predicted_frame"]`（合成环境 16×16，体积可接受）。同时在 episode 顶层加 `"spec_id"` 已有、补 `"trap"` 已有，再加 `"gen"` 由调用方注入或查表。
2. `server/main.py` 加 `GET /api/training/generations/{gen}/episodes`：返回该代全部 episode 摘要（episode_id、game、trap、solved、fool_score、steps 数、max_surprise）。store 需补 `list_episodes_by_gen(gen)`（`server/store.py`，SELECT episode_id, game, source, metrics FROM episodes WHERE gen=?，metrics JSON 解析后返回）。

前端：
3. `TrainingDashboard` 的逐代区改为可点列表/表格（每行：gen、solve、acc、ece、fool、weights），点击某代 → 右侧/下方出现该代 episodes 表（trap 徽章、solved ✓/✗、fool_score、max_surprise），点击某 episode → 打开 `EpisodeReplay`。
4. 新建 `EpisodeReplay.tsx`：读 `GET /api/training/episodes/{episode_id}`，布局复用现有模式——顶部三联图（before/predicted/actual，用 `PixelGrid`，16×16 也能画），下面步骤条（每步一格，按 surprise 着色，可点选），底部当前步决策卡（复用 A2 的决策卡子组件：gate、数学串假设、置信度、理由、belief_flips）。
5. `api.ts` 加 `fetchGenerationEpisodes(gen)`、`fetchEpisode(episodeId)`；`types.ts` 加 `TrainingEpisodeSummary`、`TrainingEpisodeDetail` 类型。

**验收**：跑一次 2 代 × 4 局训练后，能点进任一 episode 逐步查看"agent 想象了什么 → 实际发生了什么 → 假设怎么变的"；在 T1 题里能亲眼看到第 k 步惊奇飙红、假设从 `T(0,-1)` 翻转为 `T(1,0)`。

### B3. 图表升级为 SVG 折线

**文件**：`web/src/components/TrainingDashboard.tsx`、`CalibrationView.tsx`，可新建共享 `web/src/components/TrendChart.tsx`

- 手写 SVG 折线图组件 `TrendChart`（props: series[{label, points, color}], yDomain 自动 nice/可指定），带 y 轴刻度、x 轴世代号、hover 显示数值。
- Dashboard 两张图换用它：图1 solve_rate + prediction_accuracy（y 0~1）；图2 ece（y 0~max）与 fool_score（独立 y 轴或归一化后注明），解决现在 fool_score 恒顶满的失真。
- CalibrationView 的 reliability 图改为 x=claimed、y=hit_rate 的散点+连线，画 y=x 对角虚线（完美校准参照），点大小按 n。

**验收**：fool_score 曲线能看出逐代下降趋势（不再是全部 100% 的条）；reliability 图有对角线可对照。

### B4. KnowledgeView 可读化

**文件**：`web/src/components/KnowledgeView.tsx`

- 先验表的 `family` 字段是 transform spec 的 JSON 字符串（如 `{"dx":1,"dy":-1,"op":"translate"}`），前端解析后渲染成数学串 `T(1,-1)`（写一个小工具函数 `readableTransform(spec): string`，覆盖 translate/rotate/mirror/compose/periodic/其余 op 回退为 op 名；放 `web/src/utils/transform.ts`，A5 的 VectorFieldOverlay 也复用它）。
- 每行显示：动作 / 数学串 / support/total 比例条。
- 校准表沿用 B3 的 reliability 组件。

**验收**：知识库页不再出现原始 JSON 字符串，全部是 `T(1,-1)` 式数学串。

### B5. 使用引导

**文件**：`web/src/App.tsx`（或新建 `web/src/components/HelpDrawer.tsx`）、`README.md`

- 顶栏加 "?" 按钮 → 侧滑帮助抽屉，分"运行模式"与"训练模式"两节，各 5 条以内的操作步骤（配页签名）。内容要点：运行=选环境→选策略(Transform-Aware 才有函数决策)→运行→时间线选步→看决策卡/假设/想象；训练=设参数→开始→看双曲线→下钻世代/episode→知识库看学到什么。
- README"验证"节后补一节"界面导览"，与抽屉内容一致。

**验收**：新用户仅凭抽屉文案能完成"跑一局合成题并找到规则突变那一步"。

---

## WS-C 顺手修复（小，随 WS-A/B 一起提交）

- C1. `App.tsx` 运行模式默认策略改为 `transform-aware`（现在默认 heuristic-explorer，用户看不到函数式决策的另一半原因）。策略下拉每项加 `title` 描述。
- C2. `VisualGameInterface` 数据模式的 DataBlock 标题 "Obseration Input" 拼写改为 "Observation Input"。
- C3. demo.ts 的演示步骤补全 v3 字段（A5 需要 rotate/compose 假设样例；离线打开也能演示决策卡/三联图）。

---

## WS-D 算法缺口（次优先，UI 完成后另起 PR）

按 2026-07-06 训练方案审核结论，只列条目不展开，执行前先在本文件补充细化：

1. 对抗采样闭环：`trainer.py:97` 轮询采样改为按 fool_score 权重采样 + 精英参数池变异（权重已计算已入库，只差用起来）。
2. 多步规划：`imagination.py` 从单步 lookahead 升级为 depth-3 beam search（预计解锁 solve_rate 0.5 平台期）。
3. Periodic 假设合成：同一动作先后拟合出互斥函数时自动合成 `Periodic(n, f, g)` 假设。
4. 新陷阱 T2/T3（便宜，纯规则包装）；T4/T7 需先扩合成环境（干扰渲染、复杂动作）。

## 执行顺序与提交切分

1. commit 1：WS-A（A1→A2→A3→A4→A5）+ C1/C2/C3
2. commit 2：WS-B 后端部分（B2 的 trainer 存帧 + episodes API + store 查询 + 对应测试）
3. commit 3：WS-B 前端（B1→B2 前端→B3→B4→B5）
4. WS-D 另起计划细化后再动工

每个 commit 前跑 `make test && make lint && make build`；B2 后端需在 `tests/test_training.py` 补：episode steps 含 `frame/before_frame/predicted_frame` 断言 + 新端点的 TestClient 用例。

## 验证命令

```bash
make test && make lint && make build
make dev   # 手动验收各条 A/B 的"验收"项
```

手动验收主线（全部通过才算完成）：
1. 训练页设 2 代 × 4 局 → 开始 → 曲线出现。
2. 下钻 gen2 → 任一 T1 episode → 步骤条上找到红色惊奇步 → 决策卡显示假设从 `T(0,-1)` 翻转为 `T(1,0)`。
3. 回运行模式，Transform-Aware 跑一局 synth-t1 → 时间线红 tick+⚡ → 想象对比开关看三联图误差。
4. 知识库页看到 `T(0,-1)` 等数学串先验和 reliability 对角线图。
