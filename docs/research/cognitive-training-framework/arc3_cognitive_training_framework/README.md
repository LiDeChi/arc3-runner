# ARC-AGI-3 认知对抗式训练框架实现文档

版本：v0.1
目标读者：Coding Agent / 工程实现者
最终产物：一个可离线提交的 ARC-AGI-3 Player Agent，以及一套本地训练用的 Game Generator / Analyzer / Curriculum 系统。

---

## 0. 官方规则约束与工程边界

本项目面向 ARC-AGI-3。正式比赛提交必须遵守以下约束：Kaggle/competition evaluation 没有互联网访问，因此最终提交的 Player Agent 不能依赖 OpenAI、Claude、Gemini、Kimi、Qwen 等在线 API；ARC Prize 2026 页面明确写有 no internet access during evaluation，ARC Prize 2026 general conditions 也说明 Kaggle evaluation 没有互联网访问，并点名 no API-based systems like GPT/Claude/etc.。Competition Mode 还规定必须通过 API 交互、所有可用环境都计分、每个 environment 只能 make 一次、只能开一个 Scorecard、Game Reset 不允许并会变成 Level Reset。

这意味着：训练阶段可以使用 LLM / Coding Agent / 生成器 / 分析器来辅助研究，但最终提交的 agent 必须是本地可运行的算法型 agent。最终运行时可以使用程序化规则、小模型、搜索、状态图、训练阶段蒸馏出的策略模板；但不能运行时调用远程 LLM API。

官方文档还强调 ARC-AGI-3 是 interactive reasoning benchmark，目标是评估 agent 在 novel unseen environments 中探索、推断目标、构建内部模型、规划动作序列的能力。本文档的设计目标与此一致：不是写死游戏攻略，而是构建一个能在陌生游戏中快速形成规则假说并选择下一步的 Player Agent。

参考源：
- ARC Prize 2026 ARC-AGI-3 competition page: https://arcprize.org/competitions/2026/arc-agi-3
- ARC Prize 2026 general conditions: https://arcprize.org/competitions/2026
- ARC-AGI-3 Competition Mode: https://docs.arcprize.org/toolkit/competition_mode
- ARC-AGI-3 Toolkit Arcade docs: https://docs.arcprize.org/toolkit/arc_agi
- ARC-AGI-3 paper: https://arxiv.org/abs/2603.24621

---

## 1. 核心思想

本项目不把 Player 和 Generator 设计成两套无关系统，而是让二者共用同一套接近人类游戏理解的认知框架。

Player 游玩时使用这套框架从观察反推规则：它看到对象、空间、动作反馈、状态变化，然后维护多重规则假说，估计每个动作的通关收益、信息增益、步数成本、风险和不可逆性，最后选择当前最有价值的下一步。

Generator 生成游戏时使用同一套框架正向构造规则：它从对象、空间、动作、因果、目标、约束、反馈等维度组合出游戏，并专门探索三类方向：挖掘人类思维框架尚未覆盖的维度，攻击 Player 策略中忽略的方面，陷阱化 Player 过分重视的启发式。

一句话：同一认知框架，两个方向运行。生成是正向构造规则，游玩是反向猜测规则。

---

## 2. 总体架构

系统分为训练侧和提交侧。

训练侧包括 Cognitive Game Schema、Game Generator、Game Verifier、Player Agent、Trace Analyzer、Curriculum Manager、Experience Store。训练侧可以使用 LLM 或 coding agent 辅助生成、分析、重构，但训练侧不是比赛提交内容。

提交侧只包含 Competition Player Agent。它必须离线运行。它可以携带训练阶段产出的规则模板、小模型参数、启发式权重、认知本体、动作排序器、可执行搜索模块。

总体数据流如下：

```text
Shared Cognitive Game Schema
        ↓
Game Generator  →  Game Spec  →  Verifier  →  Local Training Env
        ↑                                            ↓
Curriculum Manager  ←  Trace Analyzer  ←  Player Agent
        ↓                                            ↓
Experience Store / Cognitive Profile / Strategy Templates
        ↓
Distill to Offline Competition Player
```

最终比赛运行流如下：

```text
ARC Environment Observation
        ↓
Observation Parser
        ↓
Per-game Workspace: objects, state graph, transitions, hypotheses
        ↓
Cognitive Schema Mapper
        ↓
Rule Hypothesis Engine + Causal Tester
        ↓
Action Evaluator: success + information gain - cost - risk - irreversibility
        ↓
Planner / Explorer / Meta Controller
        ↓
Next Action
```

---

## 3. 共享认知框架：Cognitive Game Schema

Cognitive Game Schema 是本项目的中心。它不是具体某个游戏的规则，而是描述人类如何理解游戏的一套基础本体。

基础槽位如下：Object、Space、Agent、Action、Causality、Goal、Constraint、Feedback、Time、Risk、Memory、Meta-rule。

Object 表示可被识别和追踪的实体，例如玩家、自身、墙、门、钥匙、按钮、敌人、道具、奖励、陷阱、传送门、可推动物、资源。Space 表示空间位置、连通性、可达性、阻挡、邻近、对齐、路径、视线、区域边界。Agent 表示可控主体及其位置、动作空间、状态、生命、资源。Action 表示 move、wait、interact、push、collect、toggle、attack、reset 等动作。Causality 表示动作导致的变化，包括开门、关门、解锁、移动、生成、销毁、变形、传送、分数变化、死亡、胜利。Goal 表示 reach、collect、survive、eliminate、arrange、escape、maximize score。Constraint 表示步数限制、资源限制、不可逆动作、敌人运动、锁定路径、隐藏状态、临时状态。Feedback 表示视觉变化、声音/文本提示、分数变化、对象消失、新路径出现、失败信号、成功信号。Time 表示等待、周期、倒计时、窗口期、延迟因果、临时效果。Risk 表示死亡、锁死、浪费关键资源、进入不可逆坏状态。Memory 表示局内记忆、跨游戏元记忆、失败模式。Meta-rule 表示规则可能切换、规则可能组合、规则可能被伪装。

工程实现时建议把这个 schema 放在 `configs/cognitive_schema.yaml`，同时在代码中定义 dataclass 或 pydantic model，保证 Player 与 Generator 都引用同一个定义。

---

## 4. Player Agent 结构

Player Agent 是最终要提交的核心。它不是一个直接从画面输出 action 的黑箱，而是一个维护认知黑板的本地推理系统。

模块如下：Observation Parser、State Tracker、Cognitive Schema Mapper、Belief State、Rule Hypothesis Engine、Causal Tester、Action Evaluator、Planner、Explorer、Meta Controller、Experience Memory。

Observation Parser 把环境 observation 转换为对象、网格、颜色、位置、变化候选。State Tracker 维护当前游戏内的状态历史、对象轨迹、状态哈希、状态转移图。Cognitive Schema Mapper 把观察到的对象和变化映射到 cognitive schema，例如把某个蓝色静态阻挡物猜为 door/barrier，把某个绿色 tile 猜为 goal/safe/portal。Belief State 维护多个竞争性规则假说，而不是只保留一个解释。Rule Hypothesis Engine 生成目标假说、对象角色假说、动作效果假说、因果假说、失败条件假说。Causal Tester 选择最小实验来验证关键假说。Action Evaluator 给候选动作打分。Planner 在当前最可信的规则假说下规划路径。Explorer 管理未测试动作、未访问状态、关键对象周围测试。Meta Controller 在 explore、verify、plan、exploit、fallback 等模式之间切换。Experience Memory 记录当前游戏局内轨迹和同次运行中的跨游戏元策略。

Player 每步主循环：

```python
while not done and step_budget > 0:
    obs = env.observe()
    parsed = observation_parser.parse(obs)
    state = state_tracker.update(parsed)
    changes = state_tracker.diff_last_transition(last_action)

    belief.update_from_observation(state, changes, last_action)
    schema_mapper.update_object_roles(state, belief)
    hypotheses = hypothesis_engine.propose_and_score(state, belief)

    mode = meta_controller.choose_mode(state, belief, hypotheses, budget)

    if mode in ["EXPLORE", "VERIFY"]:
        intent = causal_tester.choose_experiment(state, belief, hypotheses)
    else:
        intent = planner.choose_goal_intent(state, belief, hypotheses)

    candidate_actions = planner.ground_intent_to_actions(intent, state)
    action = action_evaluator.select_best(candidate_actions, state, belief, budget)

    result = env.step(action)
    memory.record(obs, state, belief, hypotheses, intent, action, result)
    last_action = action
```

核心动作价值公式：

```text
value(action) =
    P(success | belief, action) * V_success
  + IG(belief, action) * V_information
  - Cost(action)
  - Risk(action)
  - Irreversibility(action)
```

早期信息增益权重大，后期通关概率权重大。风险和不可逆性始终不能忽略。

---

## 5. Player 认知黑板数据结构

Player 需要把“见到的一切”结构化存储。建议实现一个 `CognitiveBlackboard`。

```python
@dataclass
class CognitiveBlackboard:
    objects: dict[str, ObjectBelief]
    spatial_graph: SpatialGraph
    state_history: list[GameState]
    transition_graph: TransitionGraph
    goal_hypotheses: list[GoalHypothesis]
    object_role_hypotheses: dict[str, list[RoleHypothesis]]
    causal_hypotheses: list[CausalHypothesis]
    risk_map: RiskMap
    untested_actions: list[ActionProbe]
    plan_candidates: list[PlanCandidate]
    confidence_scores: dict[str, float]
    current_mode: str
```

对象表字段：`object_id, type_guess, position, appearance, dynamic, role_guess, confidence, first_seen_step, last_seen_step`。

变化表字段：`last_action, before_state_hash, after_state_hash, changed_objects, local_changes, remote_changes, possible_causes`。

规则假说字段：`hypothesis_id, rule_type, condition, effect, confidence, evidence_for, evidence_against, next_test, falsified`。

动作价值字段：`action, success_value, info_gain, cost, risk, irreversibility, total_value, explanation`。

这套数据结构要支持序列化到 JSONL，便于训练侧 Analyzer 分析。

---

## 6. Game Generator 结构

Game Generator 不是随机造游戏，而是认知对抗式游戏生成器。目标函数是：

```text
Generator Objective =
    Expand(Human Cognitive Schema)
  + Attack(Player Blind Spots)
  + Trap(Player Overweighted Heuristics)
```

也可以称为：图式扩展 × 盲区攻击 × 偏置陷阱。

Generator 由三个子生成器组成。

Schema Expander 负责从人类游戏认知框架中挖掘新维度，例如时间性、可逆性、远程因果、对象组合、空间拓扑、反馈歧义、目标伪装、规则切换。它保证训练分布足够广。

Blind-Spot Attacker 读取 Player 日志，寻找 Player 没有表示、没有测试、没有注意的维度。例如 Player 从不测试 wait，就生成必须等待才能过的门；Player 不记录 remote_changes，就生成按钮改变远处墙；Player 不建模 temporary_state，就生成临时开门机制。

Bias-Trap Designer 寻找 Player 过度依赖的启发式，并生成可学习反例。例如 Player 过度相信 green=goal，就生成绿色危险区但提供可观察线索；Player 过度相信 nearest_reward_priority，就生成近处奖励陷阱；Player 过度相信 shortest_path，就生成最短路径死亡、绕路通关。

Generator 每次生成游戏必须输出设计意图：

```json
{
  "game_id": "trap_0172",
  "generator_type": "bias_trap",
  "target": "overweighted_prior",
  "attacked_prior": "nearest_reward_priority",
  "core_rule": "near coin is a trap; distant switch opens safe path",
  "fair_clues": [
    "trap coin is surrounded by warning tiles",
    "safe path has visual linkage to switch"
  ],
  "required_cognition": [
    "delay_gratification",
    "risk_aware_exploration",
    "remote_causal_testing"
  ],
  "expected_player_error": "go directly to nearest coin",
  "expected_learning": "evaluate reward objects by context before collection"
}
```

---

## 7. 公平性与可学习性边界

Generator 可以反直觉，但不能无证据；可以设计陷阱，但不能不可学习；可以误导 Player 的强先验，但不能随机恶意；可以惩罚过早判断，但不能惩罚合理实验。

一个有效训练游戏至少满足四个条件：它违背某个 Player 强先验；它提供可被发现的证据；它允许低风险测试；它能总结出可迁移原则。

Verifier 需要检查以下内容：

```text
Solvability:
- 至少存在一条可执行解路径
- 不依赖随机运气
- 在合理动作预算内可解

Learnability:
- 关键规则有可观察线索
- 允许低风险实验
- 反馈与规则一致

Fairness:
- 不使用无迹可循的隐藏规则
- 不使用不可预见的即时死亡
- 不把视觉噪点当作唯一线索

Anti-overfit:
- 不专门利用 Player 实现漏洞
- 同一机制可以有多种表述
- 规则可以迁移到同类变体
```

---

## 8. Trace Analyzer 与 Player Cognitive Profile

Trace Analyzer 的任务不是只看成功/失败，而是比较 Generator 的真实设计规则和 Player 在游玩过程中形成的 belief trace。

要分析的问题：Player 没有测试什么？Player 过早相信了什么？Player 的哪条假说被证据反驳但没有降权？Player 是否只观察局部变化而忽略远程变化？Player 是否重复无效路线？Player 是否从失败中更新策略？

Trace Analyzer 输出 Player Cognitive Profile：

```yaml
known_strengths:
  - basic_path_planning
  - simple_key_door
blind_spots:
  - wait_action
  - remote_effect_tracking
  - enemy_period_modeling
overweighted_priors:
  - green_is_goal
  - nearest_reward_priority
  - color_matching
underweighted_priors:
  - delayed_causality
  - irreversible_action
  - temporary_state
failure_patterns:
  - premature_exploitation
  - repeated_failed_path
  - local_only_observation
rule_update_speed:
  delayed_causality: weak
  color_prior_revision: medium
```

Generator 下一轮必须显式引用这个 profile 来选择生成目标。

---

## 9. Curriculum Manager

Curriculum Manager 决定下一批训练游戏如何组成。不要只让 Generator 一直攻击同一个弱点，否则 Player 会过拟合。建议每轮任务分布如下：

```text
40% blind-spot attack games
25% bias-trap games
20% schema-expansion games
10% replay/mixed old games
5% frozen evaluation games
```

Frozen evaluation games 用于防止训练侧过拟合。Generator 和 Player 都不能根据 frozen eval 的详细失败日志直接改游戏。只允许记录总体表现。

训练阶段应该维护 Cognitive Coverage Map：

```yaml
spatial_reasoning: 0.65
causal_reasoning: 0.48
time_mechanism: 0.22
feedback_ambiguity: 0.31
goal_inference: 0.55
reversibility: 0.26
object_composition: 0.37
counterintuitive_rules: 0.42
trap_recognition: 0.29
```

Curriculum 的目标是让覆盖图逐步均衡，而不是让某个单项分数虚高。

---

## 10. 训练阶段到比赛提交的蒸馏

训练阶段可以很复杂，甚至可以用 LLM 做设计意图、日志分析、代码重构。但最终提交必须是离线 Player。

需要蒸馏的内容包括：认知本体、对象角色先验、动作价值权重、探索模板、风险模板、因果测试模板、跨游戏元记忆初始化、可选小模型权重。

最终提交包不应包含运行时 API key、网络访问代码、远程模型调用。提交包应该包含：`agent.py`、`cognitive_schema.yaml`、`strategy_templates.yaml`、可选 `weights/`、本地 parser/planner/search 代码、运行入口、单元测试。

跨游戏记忆建议只保存同一次运行中的 run-level meta-memory。每个游戏的地图、对象、具体状态图应该在进入新游戏时清空；但抽象策略可以保留，例如“不要过早相信绿色目标”“要测试 wait”“观察远程变化”“不可逆动作先评估风险”。

---

## 11. 推荐代码目录

```text
arc3_cognitive_agent/
  README.md
  pyproject.toml
  configs/
    cognitive_schema.yaml
    generator_policy.yaml
    player_defaults.yaml
    curriculum.yaml
  src/
    arc3_agent/
      __init__.py
      competition_agent.py
      player/
        observation_parser.py
        state_tracker.py
        cognitive_blackboard.py
        schema_mapper.py
        belief_state.py
        hypothesis_engine.py
        causal_tester.py
        action_evaluator.py
        planner.py
        explorer.py
        meta_controller.py
        memory.py
      generator/
        game_spec.py
        schema_expander.py
        blindspot_attacker.py
        bias_trap_designer.py
        generator_orchestrator.py
      verifier/
        solvability_checker.py
        fairness_checker.py
        learnability_checker.py
      analyzer/
        trace_schema.py
        trace_analyzer.py
        cognitive_profile.py
      curriculum/
        coverage_map.py
        curriculum_manager.py
      envs/
        local_game_runtime.py
        game_grammar.py
      storage/
        jsonl_store.py
        sqlite_store.py
  scripts/
    train_loop.py
    generate_games.py
    analyze_traces.py
    distill_player.py
    run_local_eval.py
    run_competition_smoke.py
  tests/
    test_schema.py
    test_blackboard.py
    test_hypothesis_update.py
    test_action_evaluator.py
    test_generator_fairness.py
    test_verifier_solvability.py
    test_distilled_agent_no_network.py
```

---

## 12. MVP 实现顺序

第一阶段：实现本地 toy game grammar。支持 2D 网格、玩家、墙、目标、钥匙、门、按钮、陷阱、敌人、可推动箱子、传送门、wait 动作、step budget。目标是先验证闭环，不追求和官方环境完全一致。

第二阶段：实现 Player 的 cognitive blackboard、state tracker、transition graph、rule hypotheses、action evaluator。先支持简单规则：reach goal、key-door、button-door、hazard avoidance、wait opens door。

第三阶段：实现 Trace Analyzer。它要能从 trace 中识别：未测试动作、忽略远程变化、重复失败路径、过早相信先验、没有更新假说。

第四阶段：实现 Generator 三子模块。先实现规则模板生成，不要一开始追求复杂程序合成。每个游戏必须带 design_intent。

第五阶段：实现 Verifier。至少要用 BFS/A* 或 oracle script 检查可解；用规则检查器检查是否有线索、是否允许低风险测试。

第六阶段：实现 Curriculum Manager。根据 Player Cognitive Profile 选择下一批游戏。

第七阶段：蒸馏为离线 Competition Player。去除所有训练侧依赖和网络调用，只保留本地推理模块、策略模板、小模型权重。

---

## 13. 关键验收标准

功能验收：

```text
A1. Player 能在 toy key-door 游戏中通过观察和实验推断钥匙开门。
A2. Player 能在 button-door 游戏中检测远程变化。
A3. Player 能在 wait-door 游戏中测试 wait 动作。
A4. Player 能在绿色陷阱游戏中降低 green_is_goal 的置信度。
A5. Player 能在近处奖励陷阱中避免一味 nearest_reward_priority。
A6. Analyzer 能输出 blind_spots 和 overweighted_priors。
A7. Generator 能根据 profile 生成对应攻击游戏，并输出 design_intent。
A8. Verifier 能拒绝无解、无证据、纯随机恶意游戏。
A9. Curriculum 能混合 blind-spot、bias-trap、schema-expansion、replay、frozen eval。
A10. Distilled Competition Player 在无网络环境下通过 smoke test。
```

工程验收：

```text
B1. 所有 trace 使用 JSONL 存储，可复现某次运行。
B2. 所有 game spec 有 design_intent 和 cognitive_tags。
B3. 所有 Player 决策都有 action_value breakdown。
B4. 所有 generator 输出都经过 verifier。
B5. 训练侧代码和提交侧代码可以分包。
B6. CI 中有 no-network 测试，禁止 requests/httpx/openai/anthropic 等运行时依赖出现在 competition package。
```

---

## 14. 给 Coding Agent 的首个任务

请先实现最小可运行闭环，不要先追求官方环境适配。第一版只需要本地 toy grid games。

具体任务：

1. 创建上述项目目录。
2. 实现 `CognitiveBlackboard`、`ObjectBelief`、`CausalHypothesis`、`ActionValue` 数据结构。
3. 实现一个 toy grid runtime，支持 move/wait/interact，支持 key-door、button-door、green-trap 三种游戏。
4. 实现 Player 主循环：parse → track → hypothesis → evaluate → act → record。
5. 实现 trace JSONL。
6. 实现 Analyzer，能识别至少三种失败：未测试 wait、未观察远程变化、过度相信绿色目标。
7. 实现 Generator，能根据 Analyzer 输出生成一个针对性新游戏。
8. 实现 Verifier，至少检查可解性和是否存在关键线索。
9. 写 pytest，覆盖功能验收 A1-A8 的最小版本。
10. 写 README，说明如何运行一次 train loop 和一次 local eval。

不要在 competition package 中引入任何远程 LLM/API 依赖。训练侧可以留接口，但必须明确隔离。
