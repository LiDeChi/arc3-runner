# 实现计划与验收标准

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
