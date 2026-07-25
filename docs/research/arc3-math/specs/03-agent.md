# Spec 03 — 数学思维 Agent（agent/ 模块）

符号贝叶斯 agent：假设推断（思考）+ 心理模拟（想象）+ 主动实验（求证）+ 置信度输出（可信度判断）。纯 Python，无学习权重，全部行为可解释、可回放。

## 1. 主循环（伪代码，逐条实现）

```python
def run_episode(env: EnvAdapter, cfg) -> Trace:
    obs = env.reset()
    beliefs = {a: init_belief(a) for a in env.action_space()}   # §3
    trace = Trace()
    while not obs.done:
        plan = imagine_plan(obs, beliefs, cfg)                  # §5 想象规划
        if plan.risk < cfg.tau:                                 # τ 默认 0.7
            action = design_probe(obs, beliefs, cfg)            # §6 先做实验
            intent = "probe"
        else:
            action = plan.actions[0]
            intent = "goal"
        pred, conf = predict(obs, beliefs[action])              # §4 预测+置信度
        trace.log("prediction", action, pred, conf, intent, plan)
        new_obs = env.step(action)
        surprise = update_belief(beliefs[action], obs, new_obs) # §3 贝叶斯更新
        trace.log("outcome", new_obs, surprise)
        obs = new_obs
    return trace
```

## 2. 观察处理

输入仅为网格帧（对齐真实 ARC-AGI-3）。帧间差分识别"动的东西"= agent 假定的自身；首帧用启发式（唯一的非重复色单格）。本地引擎模式下允许直接读实体列表作为 debug 通道，但默认关闭（`cfg.oracle_entities=False`）。

## 3. 假设后验（每个动作独立维护）

```python
Belief = list[tuple[prog: dict, log_w: float]]
```

- **初始化**：`enumerate_programs(max_mdl=cfg.init_mdl)`（默认 4.0，只含"习以为常"的简单程序），log_w = −mdl(prog)，归一化。
- **更新** `update_belief(belief, s, s_next)`：
  - 对每个假设算预测 ŝ = 引擎裁决语义下的 apply（含撞墙原地不动——**agent 用与引擎同一份裁决代码**，注入自己对墙的信念：v1 简化为"tile==1 即墙"为已知常识）。
  - 匹配度 m = 网格逐格一致率 ∈ [0,1]；`log_w += β·log(max(m, ε))`，β=20，ε=1e-6。确定性环境下等效于硬过滤，但保留对噪声的鲁棒。
  - 归一化。**惊讶度** `surprise = 1 − Σ_i w_i·1[ŝ_i == s_next]`（更新前权重）。
- **信念修正（陷阱识破时刻）**：若最大权重假设的近期似然崩塌（Σw < 1e-9 或连续 2 步 m<1），触发：
  1. 以全部历史观察 (s, s_next) 为过滤器，从 `enumerate_programs(max_mdl=cfg.max_mdl)`（默认 8.0）重建假设集；
  2. 若仍无一致假设 → 启用**非平稳假设**：只用最近 W=6 步观察过滤，并给 `regime_is`/`step_mod` 条件程序解禁；
  3. 记 `belief_revision` 事件（UI 红闪）。

## 4. 预测与置信度

- MAP 预测 ŝ* = 权重最高假设的输出。
- 置信度 `conf = Σ_i w_i · 1[ŝ_i == ŝ*]`（有多少后验质量同意 MAP 预测）。
- 每步把 (conf, 事后是否正确) 写入校准日志 → ECE、可靠性图（10 个等宽 bin）、Brier 分。

## 5. 想象规划器 imagine_plan

- 用每个动作的 MAP 程序构造"信念动力学"，BFS（深度 ≤ cfg.plan_depth=40，状态哈希去重）搜到达 win 的最短动作序列。
- `plan.risk = min(conf_a for a in 计划用到的动作集合)`，conf_a = 该动作 belief 的 MAP 置信度。
- `plan.imagined_states` = 逐步想象帧（发给 UI 画幽灵轨迹）。
- 搜不到解 → risk=0（强制走实验分支）。

## 6. 实验设计器 design_probe（主动求证）

在"安全动作"中选**信息增益**最大者：

- 候选：当前状态下每个动作 a，取其 belief 前 2 假设的预测 ŝ₁, ŝ₂；分歧度 d_a = 1 − match(ŝ₁, ŝ₂)，再乘不确定度 (1 − conf_a)。
- 安全过滤：所有假设的预测位置都不落在 lava/未知致死 tile 上；不安全的动作分数 ×0.1。
- 选 argmax；全零（都很确定但仍无解）→ 选择探索计数最少的动作（平票取动作序号最小，保持确定性）。
- 事件记 `intent: "probe"`，UI 时间轴上用不同颜色标出——**你能直观看到 agent "先做实验再行动"的可信度行为**。

## 7. SFT 数据导出（M4，为训练 LLM agent 铺路）

`arena/export_sft.py`：把已解决 episode 的轨迹转成 JSONL，每行：

```json
{"messages": [
  {"role": "system", "content": "你是空间变换推理agent。动作是未知的空间变换函数..."},
  {"role": "user", "content": "<最近K步观察，网格渲染为字符画>\n问题：给出每个动作的最优假设(DSL JSON)、置信度、下一步行动及理由。"},
  {"role": "assistant", "content": "<符号agent的真实假设/置信度/行动，含 program_to_math 记号>"}
]}
```

符号 agent 在这里充当**教师**：它的每一步推理都是结构化的，天然是高质量思维链数据。用这份数据可 SFT 任意 LLM，让其学会同样的函数式思考风格（LLM 集成本身不在 M0-M4 范围内）。

## 8. 测试要求

- `tests/test_agent.py`：
  - g01：≤ 10 步解决，全程无 belief_revision；
  - g03（镜像）：出现 ≥1 次 belief_revision，最终每个用到的动作后验 top1 与真值程序**外延等价**；
  - g05（分区）：出现 ≥1 次 `intent:"probe"` 事件；
  - 校准日志非空且 ECE 可计算。
- 确定性：同 seed 同游戏两次运行 trace 完全一致。
