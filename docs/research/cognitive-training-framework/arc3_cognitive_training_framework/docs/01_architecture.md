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
