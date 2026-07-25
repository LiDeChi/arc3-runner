# Generator / Analyzer / Curriculum 详细设计

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
