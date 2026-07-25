# Player Agent 详细设计

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
