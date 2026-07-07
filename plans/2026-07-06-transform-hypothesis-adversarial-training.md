# 变换函数假设 + 对抗式合成训练方案（Transform-Hypothesis Adversarial Training）

## 目标

把当前 `server/main.py` 里的"未试优先 + 信息增益"启发式 agent，重构为一个**以空间变换函数为思维单位**的可训练 agent，并配套一个**对抗式游戏合成器**和**训练全流程可视化界面**：

1. Agent 把每个动作理解为一个数学变换函数（如 `ACTION1 ≙ T(0,-1)` 即"向上 = y 坐标减一"）。观察不符时，用函数组合解释（如"斜向上 = R45 ∘ T(0,-1)"，或"控制被旋转了 90°"）。
2. Agent 用这些函数做**前向想象（imagination）**：先在脑内推演每个候选动作的结果，再选真实动作；事后对比"想象 vs 实际"，产生**惊奇（surprise）**信号并修正假设。
3. **对抗式合成器**用同一套变换词汇合成新游戏，专门针对 agent"习以为常"的函数设陷阱（前 k 步符合常识、之后规则突变等），迫使 agent 学会**可信度判断（calibration）**——知道自己什么时候该信自己的假设，什么时候该怀疑。
4. 界面新增"训练"模式，让人能直观看到：每个动作当前的假设函数、想象帧 vs 实际帧、惊奇事件、可信度曲线、合成游戏画廊、逐代对抗成绩。

## 非目标（第一期）

- 不引入神经网络。第一期全部用**可审计的符号假设 + 贝叶斯计数**实现"学习"，与本项目"结构化审计、不藏思维链"的定位一致。神经网络留 v2 钩子。
- 不改官方 Toolkit 的调用方式；官方环境只做**评测**，训练主要在本地合成环境上进行（避免 API 限速，且合成环境才有可控陷阱）。
- 不做分布式训练。单进程、SQLite 持久化即可。

## 当前分支执行状态（2026-07-07）

- 已切到 `claude/project-overview-xj2b52` 的干净本地 checkout：`/Users/lidechi/Documents/Github/worktrees/arc3-runner/project-overview-xj2b52`。
- M0 契约先行：已扩展 `TraceStep` audit.v3 字段和 Training 类型；`demo.ts` 已加入 hypotheses/imagination/surprise/credibility 演示数据。
- M1 变换 DSL：已新增 `server/transforms.py` 与 `tests/test_transforms.py`，覆盖基元 apply/序列化/可读串/复杂度/组合。
- M2 影子模式：已新增 `server/hypothesis.py` 与 `tests/test_hypothesis.py`；`server/main.py` 在不改变旧启发式策略的前提下写入假设、想象帧、惊奇、可信度事件；`VisualGameInterface`、`HypothesisPanel`、`ImaginationView` 和 `EventDetail` 已能显示这些字段，`VectorFieldOverlay` 提供 translate 假设的向量示意。
- M3 变换感知策略：已新增 `server/imagination.py` 与 `server/policy.py`；`POST /api/runs` 可传 `agent: "transform-aware"`；运行时按假设置信度在 exploit/probe 间切换，并把 decision-time plan tree 写入 audit.v3 事件；`tests/test_policy.py` 覆盖策略路由。
- M4 合成环境与陷阱库（后端）：已新增 `server/synth_env.py` 与 `server/traps.py`；内置 T1/T6 合成题；`GET/POST /api/synth/specs` 与 `GET /api/synth/specs/{spec_id}` 可列出、创建、读取 GameSpec；`synth-*` 游戏可通过现有 run loop 执行；`tests/test_synth_env.py` 覆盖规则突变、伪装偏移和 API。
- M4 专用 SynthFactory 前端页签：已新增训练模式与 `SynthFactory.tsx`，支持查看合成题画廊、GameSpec JSON、生成 T1/T6、直接创建 synth-local run。
- M5 对抗训练循环与 SQLite：已新增 `server/store.py`、`server/trainer.py` 和 `/api/training/*`；训练会采样 T1/T6 合成题、执行 transform-aware episode、计算 solve_rate/prediction_accuracy/ECE/fool_score、写入 SQLite；前端已新增 TrainingDashboard、CalibrationView、KnowledgeView；`tests/test_training.py` 覆盖 store、episode、训练 API；训练知识会回灌到后续合成 episode，动作先验只记录非 identity 变换，可信度使用连续 `1 - surprise` 校准口径。
- M6 官方环境对照评测：trainer 已支持每 N 代触发官方公开环境对照评测 hook；`RunnerRuntime.evaluate_official_agents()` 可在有官方环境访问时对 Heuristic Explorer、原始 Transform-Aware、训练后 Transform-Aware 运行有界对照并报告 solve_rate、prediction_accuracy、ECE、delta 和 trained_delta；官方评测只迁移训练得到的校准策略，不把合成动作先验直接套到官方 action_id 上；TrainingDashboard 会显示官方评测报告；README 已更新；离线测试用 fake evaluator 覆盖持久化与报告链路。
- 验收证据（2026-07-07）：本地合成训练 `generations=10, games_per_gen=12` 后，solve_rate 从 0.1667 到 0.5，ECE 从 0.0377 到 0.0057，fool_score 从 4.9704 到 3.2988；匿名官方公开环境对照 `max_games=5, max_actions=20` 后，Transform-Aware 与 Heuristic Explorer 持平（delta 全 0），训练后 Transform-Aware 相比原始 Transform-Aware 的 solve_rate delta 0.0、prediction_accuracy delta 0.0、ECE delta -0.1234（0.2435 → 0.1201）。运行中第 5 个官方环境曾出现一次 transient SSL EOF，官方 toolkit 重试后成功完成报告。

## 现状依据

- `server/main.py:339` `_choose_action`：现有 UCB 式启发策略，将被新策略替换（保留为 `heuristic-explorer` 备选）。
- `server/main.py:643` `_extract_components`：连通区域提取，可直接复用为"对象抽取"。
- `server/main.py:280-288`：novelty 奖励 `log1p(changed_cells) + 20*level_gain`——注意它可被"干扰性闪烁"陷阱毒化，这正是对抗合成的靶点之一。
- `server/main.py:418` `_build_step`：步骤事件 schema（`arc3-runner.audit.v2`），需要扩展为 v3。
- `web/src/components/EventDetail.tsx`：七种详情视图，是新增"假设/想象/可信度"视图的挂载点。
- `web/src/types.ts`：前端数据契约。
- 运行状态目前纯内存（README"生产化"一节），训练需要跨局持久化，引入 SQLite。

---

## 一、核心概念与数据定义

### 1.1 变换基元 DSL（Transform DSL）

所有"动作效果"和"游戏规则"共用一套基元。每个基元有：参数、`apply(objects|grid) -> grid`、复杂度代价（MDL 用）、人类可读的数学串。

```
基元                 数学串示例          复杂度   说明
Translate(dx, dy)    T(0,-1)            1       平移；"向上"即 T(0,-1)
Rotate(k, pivot)     R90@obj            2       绕质心/固定点旋转 90k°
Mirror(axis)         M(x)|M(y)|M(diag)  2       镜像
Scale(f)             S(2)               2       整数缩放
ColorMap(π)          C{3→5}             1+|π|   颜色置换
Identity             I                  0       无效果
Toggle(cell_set)     G{...}             3       指定格集合翻转
Compose(f, g)        R90 ∘ T(0,-1)      f+g+1   函数组合
Conditional(pred,f,g) if in Ω: f else g 3+f+g   分区/条件变换（陷阱常用）
Periodic(n, f, g)    [f]*n then g       3+f+g   前 n 步 f、之后 g（规则突变陷阱）
```

序列化为 JSON（示例）：

```json
{"op": "compose", "fs": [
  {"op": "rotate", "k": 1, "pivot": "object"},
  {"op": "translate", "dx": 0, "dy": -1}
]}
```

### 1.2 假设（Hypothesis）

"某动作（在某上下文）等价于某变换函数"的一条候选解释：

```json
{
  "hypothesis_id": "h-a1-3",
  "action_id": 1,
  "scope": {"object_selector": "avatar", "region": null},
  "transform": {"op": "translate", "dx": 0, "dy": -1},
  "readable": "ACTION1 ≙ T(0,-1) on avatar",
  "support": 14, "violations": 1,
  "confidence": 0.87,
  "complexity": 1,
  "source": "fit@step12"
}
```

- `confidence` 用 Beta 后验均值：`(support+1)/(support+violations+2)`，再乘一个时间衰减（最近违背权重更高），保证规则突变后置信度快速下跌。
- 每个 `action_id` 维护一个按 `score = confidence - λ·complexity`（λ≈0.05）排序的假设列表，Top-1 为"当前信念"。

### 1.3 惊奇（Surprise）与可信度事件

每一步执行前，用 Top-1 假设生成**想象帧**；执行后对比实际帧：

```
pixel_error   = 想象与实际不同的格数 / 变化格数上界
object_error  = 匹配后对象级误差（位置/颜色/存在性）
surprise      = 1 - 预测精确度（0=完全预中，1=完全预错）
```

`surprise > τ`（τ≈0.3）记为一次**惊奇事件**，触发：降低该假设置信度 → 重新拟合 → 若新旧假设换位，记录"信念翻转"事件。这些事件是可信度界面的主数据。

### 1.4 陷阱分类（Trap Taxonomy）——对抗合成的武器库

| 编号 | 名称 | 构造 | 打击的先验 |
|---|---|---|---|
| T1 | 规则突变 | `Periodic(n, T(0,-1), T(1,0))`：前 n 步正常，之后向上变向右 | "规则恒定" |
| T2 | 控制旋转 | 全部方向键统一被 `R90` 包裹 | "按钮语义 = 常识方向" |
| T3 | 分区规则 | `Conditional(x>32, M(y)∘f, f)`：右半屏控制镜像 | "规则全局一致" |
| T4 | 干扰闪烁 | 每步随机翻转一块与目标无关的区域 | novelty 奖励（毒化 `changed_cells`） |
| T5 | 延迟生效 | 动作效果推迟 1 步显现 | "因果即时性" |
| T6 | 伪装偏移 | 前 k 步完全符合 `T(0,-1)`，第 k+1 步起变 `T(0,-1)∘T(1,0)` | "高置信 = 永远正确"（专攻过度自信） |
| T7 | 假目标 | 视觉上像目标的诱饵对象，点击则退关 | "显著区域 = 值得点击" |

每个陷阱是一个**参数化模板**；合成器学的就是"哪种模板、什么参数最能骗到当前 agent"。

### 1.5 Agent 学到的东西（跨局持久化的"权重"）

1. **动作先验表** `prior(action_id, context_features) -> P(transform_family)`：贝叶斯计数。例如"历史上 ACTION1 有 78% 的游戏里是纯平移"。新游戏开局用它做冷启动猜测。
2. **校准参数**：把原始 confidence 映射为校准后概率的单调回归表（用历史"声称置信度 vs 实际命中率"拟合，Isotonic 或分桶）。
3. **陷阱特征库**：每类陷阱被识破时的前兆特征（如"高置信假设连续 2 次小幅偏差"预示 T6），作为怀疑触发器。

三者全部是可打印的表/计数，界面上直接可视。

---

## 二、架构总览

```
                        ┌────────────────────────────────────────────┐
                        │                trainer.py                  │
                        │  对抗训练循环：出题 → 作答 → 评分 → 更新     │
                        └──────┬─────────────────────────┬───────────┘
                               │ 合成游戏                 │ 运行请求
                    ┌──────────▼──────────┐   ┌──────────▼──────────┐
                    │     synth_env.py    │   │  main.py (Runner)   │
                    │  本地合成环境引擎     │   │  官方env / 合成env    │
                    │  + traps.py 陷阱库   │   │  统一 step 接口      │
                    └─────────────────────┘   └──────────┬──────────┘
                                                         │ 帧/响应
                              ┌──────────────────────────▼──────────┐
                              │            agent 包                  │
                              │ transforms.py  变换DSL               │
                              │ hypothesis.py  拟合+置信度            │
                              │ imagination.py 前向想象+规划          │
                              │ policy.py      变换感知策略           │
                              └──────────────┬───────────────────────┘
                                             │ 假设/想象/惊奇 事件
                              ┌──────────────▼───────────────────────┐
                              │ store.py  SQLite: 先验/校准/世代/回合  │
                              └──────────────┬───────────────────────┘
                                             │ /api/training/*
                              ┌──────────────▼───────────────────────┐
                              │ web  训练模式界面（第四节）             │
                              └──────────────────────────────────────┘
```

新增后端文件（`server/` 下，均为纯 Python + numpy，无新重依赖）：

```
server/transforms.py    变换 DSL：基元、apply、复杂度、序列化、可读串
server/hypothesis.py    对象匹配、假设拟合、置信度与惊奇
server/imagination.py   前向想象、规划（beam search）
server/policy.py        transform-aware 策略（并保留 heuristic-explorer）
server/synth_env.py     合成环境引擎（与官方 env 同构接口）
server/traps.py         陷阱模板库 + 参数采样
server/trainer.py       对抗训练循环 + 世代管理
server/store.py         SQLite 持久化
```

---

## 三、算法细节（手把手）

### 3.1 对象匹配与假设拟合（hypothesis.py）

输入：前帧对象列表 `A`、后帧对象列表 `B`（复用 `_extract_components`）。

1. **匹配**：构造代价矩阵 `cost[i][j] = w1·质心距离 + w2·|size差| + w3·颜色不等 + w4·形状哈希不等`，用匈牙利算法（`scipy.optimize.linear_sum_assignment`，scipy 已随 arc-agi 依赖链存在；否则手写贪心即可）得到对应关系；剩余未匹配者标记"出现/消失"。
2. **单对象拟合**：对每对 `(a, b)`，在基元库中枚举拟合：
   - 平移：`dx = b.cx - a.cx, dy = b.cy - a.cy`，校验整块像素平移一致。
   - 旋转/镜像：把 `a` 的包围盒像素做 R90/R180/R270/M(x)/M(y) 后与 `b` 比对。
   - 颜色映射：形状全等但颜色不同。
   - 组合：先旋转再平移（两层组合封顶，防爆炸）。
3. **全局假设**：多数对象服从同一函数 → "全局变换"；只有 avatar（=帧间最常移动的对象）服从 → "avatar 变换"；按区域分裂 → 生成 `Conditional` 假设。
4. **打分入库**：`score = confidence - λ·complexity`。同一动作的历史观测都参与 support/violation 累计；`Periodic` 假设由"同一动作先后拟合出两个互斥函数"自动合成。

伪代码：

```python
def observe(action_id, before_objs, after_objs, store):
    pairs, appeared, vanished = match(before_objs, after_objs)
    fits = enumerate_transforms(pairs, appeared, vanished)   # -> [Transform]
    for h in store.hypotheses(action_id):
        h.update(consistent=any(f.equals(h.transform) for f in fits))
    for f in fits:
        store.upsert_hypothesis(action_id, f)
    return SurpriseReport(...)
```

### 3.2 想象与规划（imagination.py）

- `imagine(frame, hypothesis) -> ghost_frame`：把 Top-1 假设应用在当前帧的对象上，渲染出预测帧。逐动作生成一排"幽灵帧"。
- `plan(frame, goal_hint, depth=3, beam=5)`：以校准后置信度为转移概率，beam search 展开想象树；节点效用 = `Σ 路径置信度 × 启发式进展分`（进展分：目标对象与 avatar 距离缩短、关卡计数特征等）。返回最优首动作 + 整棵想象树（供界面渲染）。
- **可信度门控**：路径置信度 < θ（θ≈0.5）时放弃规划，退回"实验模式"——选择**信息价值最大**的动作（最能区分互斥假设的那一个），这就是"懂得怀疑之后主动做实验"。

### 3.3 变换感知策略（policy.py）

每步决策流程（写进步骤事件，界面可完整回放）：

```
1. 感知     对象抽取 + 与上一帧匹配
2. 复盘     用上一步的想象帧对比实际帧 → surprise → 更新假设/置信度
3. 冷启动   若某动作无假设，用先验表给出初始猜测（含置信度）
4. 决策     若 max路径置信度 ≥ θ → 执行 plan 首动作（exploit）
            否则 → 执行区分度最大的实验动作（probe）
5. 预测     对将执行的动作生成想象帧，存入事件（下一步复盘用）
```

替换 novelty 奖励：进展奖励只认 `level_gain` 与"假设收敛度提升"，`changed_cells` 仅作为惊奇分母——这直接免疫 T4 干扰闪烁陷阱。

### 3.4 合成环境（synth_env.py）

与官方 env 同构的最小接口（Runner 无需分支逻辑）：

```python
class SyntheticEnv:
    observation_space   # 同官方：frame/state/levels_completed/win_levels/available_actions
    action_space        # 同官方：Action 枚举，含 is_complex()
    def step(self, action, data=None, reasoning=None) -> Observation
```

游戏定义（GameSpec，JSON 可存库、可在界面展示）：

```json
{
  "spec_id": "synth-g42",
  "grid": 64, "avatar": {"color": 4, "start": [10, 50]},
  "goal": {"type": "reach", "target": [55, 8]},
  "rules": {"1": {"op": "translate", "dx": 0, "dy": -1}, "...": "..."},
  "traps": [{"template": "T6", "params": {"k": 9, "drift": [1, 0]}}],
  "max_steps": 80, "win_levels": 1
}
```

### 3.5 对抗合成器与训练循环（traps.py + trainer.py）

合成器不是随机出题，它的目标函数是**最大化 agent 的"过度自信错误"**：

```
fool_score(game) = Σ_steps  claimed_confidence × surprise      （骗到高置信预测才得分）
                 + 5 × (agent 未通关 ? 1 : 0)
```

每个世代（generation）：

```
1. 出题   每个陷阱模板按当前权重采样 M 局（初始均匀），参数做局部变异
          （在上一代 fool_score 最高的参数附近扰动）
2. 作答   agent 逐局游玩（走完整决策流程，事件全存）
3. 评分   agent 侧：solve_rate、预测精确度、ECE 校准误差、惊奇恢复步数
          合成器侧：每局 fool_score
4. 更新   agent：先验表计数更新 + 校准表重拟合 + 陷阱前兆特征入库
          合成器：模板权重 ∝ 平均 fool_score（softmax），高分参数进精英池
5. 落库   世代汇总 + 全部回合事件 → SQLite；触发前端刷新
```

对抗平衡的健康标志：fool_score 逐代下降后，合成器被迫换模板/换参数，agent 的 ECE 持续下降——这就是"可信度判断"被训练出来的直接证据，界面上用双曲线呈现。

**评测（不训练）**：每 5 个世代在官方公开环境跑一轮对照（transform-aware vs 旧 heuristic-explorer），验证合成训练迁移到真实环境。

### 3.6 持久化（store.py，SQLite 单文件 `data/runner.db`）

```sql
CREATE TABLE priors        (action_key TEXT, family TEXT, support INT, total INT, PRIMARY KEY(action_key, family));
CREATE TABLE calibration   (bucket REAL PRIMARY KEY, claimed REAL, hit_rate REAL, n INT);
CREATE TABLE generations   (gen INT PRIMARY KEY, created_at TEXT, agent_metrics TEXT, gen_metrics TEXT, weights TEXT);
CREATE TABLE synth_games   (spec_id TEXT PRIMARY KEY, gen INT, spec TEXT, fool_score REAL, solved INT);
CREATE TABLE episodes      (episode_id TEXT PRIMARY KEY, gen INT, game TEXT, source TEXT, metrics TEXT, steps_blob TEXT);
CREATE TABLE trap_signals  (trap TEXT, signature TEXT, hits INT, PRIMARY KEY(trap, signature));
```

### 3.7 API 扩展（main.py 挂载）

```
POST /api/training/start        {generations, games_per_gen, trap_filter?}
POST /api/training/stop
GET  /api/training/status       当前世代、进行中的局、实时指标
GET  /api/training/generations  世代列表 + 双方指标曲线数据
GET  /api/training/generations/{gen}/games      本代合成游戏画廊
GET  /api/training/episodes/{episode_id}        单局完整回放（复用现有 run 详情结构）
GET  /api/training/knowledge    先验表 + 校准表 + 陷阱特征库（agent 的"脑"）
GET  /api/synth/specs/{spec_id} 合成游戏定义 JSON
POST /api/runs                  扩展 agent 字段: "transform-aware" | "heuristic-explorer"
```

步骤事件 schema 升级为 `arc3-runner.audit.v3`，每步新增：

```json
{
  "hypotheses": [{"action_id": 1, "readable": "T(0,-1)", "confidence": 0.87, "alternatives": ["R90∘T(0,-1): 0.11"]}],
  "imagination": {"predicted_frame": [["..."]], "plan_tree": {"...": "..."}, "mode": "exploit|probe"},
  "surprise": {"value": 0.05, "pixel_error": 3, "object_error": 0, "belief_flips": []},
  "credibility": {"claimed": 0.87, "calibrated": 0.79, "gate": "exploit"}
}
```

---

## 四、界面设计（训练全流程可视化）

顶栏在现有布局上加一个模式开关：`运行 | 训练`。运行模式 = 现有界面不动；训练模式 = 以下五个页签。

### 4.1 页签 ① 训练总览（TrainingDashboard.tsx）

```
┌──────────────────────────────────────────────────────────────────┐
│ 世代 12 / 20   ●训练中   本代 7/16 局    [开始] [停止] [参数▾]     │
├────────────────────────┬─────────────────────────────────────────┤
│  通关率 & 预测精确度曲线  │   对抗双曲线                             │
│  （逐代折线，两条）        │   agent ECE ↓  vs  合成器 fool_score ↓  │
│                        │   （剪刀差收敛 = 训练有效）                │
├────────────────────────┴─────────────────────────────────────────┤
│ 实时流：正在玩 synth-g42 (T6 伪装偏移)  step 14/80  surprise 0.62 ⚠ │
│         [缩略帧] [缩略帧] [缩略帧] ...   ← 点击跳入单局回放           │
└──────────────────────────────────────────────────────────────────┘
```

### 4.2 页签 ② 假设与想象（HypothesisPanel.tsx + ImaginationView.tsx）

进入任意一局（合成或官方）的步骤后，在现有 EventDetail 七个视图旁新增两个视图：

**"假设"视图** —— 每个可用动作一行：

```
ACTION1  ≙ T(0,-1) on avatar     ████████░░ 0.87   备选: R90∘T(0,-1) 0.11 | I 0.02
ACTION2  ≙ T(0,+1) on avatar     █████████░ 0.93
ACTION6  ≙ Toggle@click 区域      ███░░░░░░░ 0.31   (实验中)
```

- 点一行，在主帧上叠加**向量场箭头**：该假设作用于各对象的位移/旋转示意。
- 置信度条按"校准后概率"着色（绿→黄→红），旁边小字标原始声称值。

**"想象"视图** —— 三联图 + 规划树：

```
┌─ 上一帧 ─┐   ┌─ 想象帧(ghost) ─┐   ┌─ 实际帧 ─┐
│  frame   │ → │  半透明预测      │ ⇄ │  frame   │   误差热力: 红=预错格
└──────────┘   └─────────────────┘   └──────────┘
 规划树: ○─ACTION1(0.87)─○─ACTION1(0.76)─◎goal   ← 幽灵缩略帧串成的树，
        └ACTION3(0.42)─○ ...                       最优路径高亮
 本步模式: EXPLOIT（路径置信 0.66 ≥ θ0.5）
```

### 4.3 页签 ③ 可信度（CalibrationView.tsx）

```
┌ 惊奇时间线：整局一条色带，每步一格，白→红=surprise，⚡=信念翻转 ────┐
├ 各动作置信度曲线：多条折线随步数演化；T1/T6 触发处能看到断崖下跌   ┤
├ 校准图(reliability diagram)：x=声称置信度分桶 y=实际命中率，       │
│   对角线=完美校准；训练前后两条曲线对比，直观看到"变谦虚了"        │
└ 惊奇恢复：每次惊奇事件后多少步重建可用假设（越短越好，逐代柱状图） ┘
```

### 4.4 页签 ④ 对抗工厂（SynthFactory.tsx）

```
┌ 本代合成游戏画廊（卡片网格）─────────────────────────────────────┐
│ [缩略帧] synth-g42   陷阱: T6 伪装偏移(k=9)                       │
│  agent: ✗ 未通关   fool_score 4.7 ▲   声称置信0.9时被骗 3 次      │
│  [回放] [查看 GameSpec JSON] [手动再出一题▾(调参重生成)]           │
├ 陷阱 × 弱点热力图 ──────────────────────────────────────────────┤
│        T1   T2   T3   T4   T5   T6   T7                          │
│ 第5代  ██   █    ▒    ██   █    ███  ▒     ← 越红=越容易被骗       │
│ 第12代 ▒    ▒    ░    ░    ▒    █    ░     ← 弱点被逐代修复        │
├ 合成器状态：模板权重分布条形图 + 精英参数池列表 ────────────────────┤
└──────────────────────────────────────────────────────────────────┘
```

卡片点"回放"直接进入 4.2/4.3 的单局审计——合成局与官方局共用同一套回放组件。

### 4.5 页签 ⑤ 知识库（KnowledgeView.tsx）

Agent 的"脑"随时可查：先验表（每个动作语义 → 变换族概率条形图）、校准映射表、陷阱前兆特征列表（如 `T6: 高置信假设连续2次偏差≤2格 → 提升怀疑`）。每项都标注来源世代，可追溯。

### 4.6 前端文件清单

```
web/src/types.ts                      扩展 TraceStep(v3字段) + Training* 类型
web/src/api.ts                        新增 /api/training/* 封装 + 轮询
web/src/components/TrainingDashboard.tsx
web/src/components/HypothesisPanel.tsx
web/src/components/ImaginationView.tsx     （复用 PixelGrid 做 ghost 叠加）
web/src/components/CalibrationView.tsx
web/src/components/SynthFactory.tsx
web/src/components/KnowledgeView.tsx
web/src/components/VectorFieldOverlay.tsx  （SVG 箭头层，叠在 PixelGrid 上）
web/src/App.tsx                       模式开关 + 训练页签路由
web/src/demo.ts                       追加训练模式离线演示数据
```

刷新机制沿用现有轮询模式（`GET /api/training/status` 每 1s），不引入 WebSocket。

---

## 五、实施里程碑（按顺序执行，每步可独立验收）

### M0 — 契约先行（0.5 天）
- `web/src/types.ts`、`server/main.py` 定义 audit.v3 字段与 Training 类型；`demo.ts` 加一局带 hypotheses/imagination/surprise 假数据的演示局。
- **验收**：`make build` 过；离线打开前端能看到新字段渲染占位。

### M1 — 变换 DSL（1 天）
- 写 `server/transforms.py` + `tests/test_transforms.py`：每个基元的 apply/序列化/可读串/复杂度；组合与相等判断。
- **验收**：`make test` 全绿；`python -c` 里 `Compose(Rotate(1),Translate(0,-1)).readable() == "R90 ∘ T(0,-1)"`。

### M2 — 假设引擎 + 影子模式（2 天）★ 第一个"看得见"的里程碑
- 写 `hypothesis.py`（匹配、拟合、置信度、惊奇）；在 `_execute_game` 里**影子接入**：策略仍用旧启发式，但每步照常拟合假设、生成想象帧、算 surprise，全部写入事件。
- 前端上 HypothesisPanel + ImaginationView 两个视图。
- **验收**：跑任一官方环境，逐步能看到"假设列表 + 三联图 + 误差热力"；假设在几步内收敛到合理的 T(dx,dy)。

### M3 — 变换感知策略（2 天）
- 写 `imagination.py`（规划）+ `policy.py`；`POST /api/runs` 支持 `agent: "transform-aware"`；exploit/probe 门控落地。
- **验收**：同一官方游戏上 transform-aware 与 heuristic-explorer 各跑 3 局，前者步均预测精确度 > 0.7，且事件里能看到 probe/exploit 切换理由。

### M4 — 合成环境 + 陷阱库（2 天）
- 写 `synth_env.py` + `traps.py` + `tests/test_synth_env.py`；`GET /api/synth/specs`、手动出题接口；前端 SynthFactory（先只有画廊+回放，无进化）。
- **验收**：手动生成 T1/T6 各一局让 agent 玩，在可信度视图能看到置信度断崖 + 信念翻转标记。

### M5 — 对抗训练循环 + 持久化（3 天）
- 写 `trainer.py` + `store.py`；训练 API 全套；TrainingDashboard / CalibrationView / KnowledgeView 上线。
- **验收**：`POST /api/training/start {generations:10, games_per_gen:12}` 一键跑完；总览页看到 ECE 逐代下降、fool_score 剪刀差；重启服务后知识库仍在。

### M6 — 官方环境对照评测（1 天）
- trainer 里加每 5 代的官方评测钩子；README 更新。
- **验收**：`make test && make lint && make build` 全过；评测报告显示训练后 agent 在官方环境的通关率/预测精确度不低于训练前，ECE 显著下降。

## 六、指标口径（界面与验收共用）

- **预测精确度** = 1 − pixel_error（对象级另列）。
- **ECE**（期望校准误差）= Σ_b (n_b/N)·|声称置信度_b − 命中率_b|，10 桶。
- **惊奇恢复步数** = 惊奇事件后，重新出现 confidence ≥ 0.7 假设所需步数。
- **fool_score** 见 3.5；**剪刀差收敛** = 连续 3 代 agent ECE 下降且合成器最优 fool_score 不升。

## 七、风险与对策

| 风险 | 对策 |
|---|---|
| 对象匹配脆弱（对象重叠/大面积重绘） | 匹配失败时退化为整帧差异假设 `Toggle`，标低置信度，不污染先验 |
| 组合空间爆炸 | 组合封顶两层；先按先验表排序枚举，命中即停 |
| 合成器过强导致 agent 学不动 | 世代内保留 30% "上一代已解出"的题目作课程锚点（curriculum anchor），防难度失控 |
| novelty 奖励毒化 | M3 起奖励只认 level_gain + 假设收敛度（3.3） |
| 官方 API 限速 | 训练全在本地合成环境；官方环境只做每 5 代评测 |
| SQLite 写入阻塞请求线程 | trainer 独立线程 + 批量写；API 只读快照 |

## 八、验证命令

```bash
make test    # transforms / hypothesis / synth_env / trainer 单测
make lint
make build
make dev     # 手动：训练页签跑 2 个世代，逐视图核对第四节的呈现
```
