# Spec 07 — 里程碑、验收标准与执行守则

## 0. 执行守则（每次交给执行模型时原样附上）

1. **只做当前里程碑**的任务，不预支后面的功能。
2. 技术栈与 JSON schema 以 specs 为准，**不得擅自更换依赖或修改 schema**；发现 spec 有矛盾/缺口，停下来在交付说明里列出问题，不要自行发明。
3. 一切随机性必须显式 seed；两次运行结果必须逐位一致。
4. 每个模块交付时附 pytest 测试；提交前 `make test` 全绿并贴出完整输出。
5. 代码里不留 TODO 空壳函数；实现不了就在交付说明里说明。
6. 文件放在 spec 05/PLAN 规定的目录结构里，命名不自创。
7. 前端不引入组件库（antd/mui 等）；图表只用 recharts；样式手写 CSS。
8. 验收命令输出必须原样贴在交付说明末尾。

## M0 — 脚手架 + DSL（预计 1 个会话）

交付：目录结构（PLAN §5）、`pyproject.toml`（fastapi/uvicorn/numpy/pytest）、`Makefile`（test/dev-api/arena 三个目标，先占位后两个）、完整 `dsl/` 模块（spec 01 全部）。

验收：

```bash
cd backend && python -m pytest tests/test_dsl.py -v     # 全绿
python -c "from arc3math.dsl import enumerate_programs; print(len(enumerate_programs(8.0)))"  # 200~5000
```

含共轭定律参数化测试（spec 01 §6）全部通过。

## M1 — 引擎 + 手写游戏 + Agent + CLI 回放（1~2 个会话）

交付：`engine/`（spec 02）、5 个手写游戏 + `solutions.json`、`agent/`（spec 03）、`arena/cli.py`：`python -m arc3math.arena.cli --game games/g03_mirror.json` 跑一局并把事件流（spec 05 §2 的 JSON，每行一条）写到 stdout/文件。

验收：

```bash
python -m pytest tests/test_engine.py tests/test_agent.py -v
python -m arc3math.arena.cli --game games/g03_mirror.json --out /tmp/trace.jsonl
# 断言脚本检查: result=win, 存在 belief_revision 事件, 事件顺序符合 spec 05 §2
```

5 个游戏全部 win；g03 出现信念修正；g05 出现 probe 事件。

## M2 — 后端服务 + 回放 UI（2 个会话：后端 1 + 前端 1）

交付：`arena/db.py + loop.py`、`api/`（spec 05 REST+WS，game_source=handwritten）、frontend 脚手架 + 顶栏 + **Episode Viewer 完整实现**（spec 06 §2），其余 Tab 占位。

验收：

```bash
make dev-api &  # :8321
cd frontend && npm run dev  # :5173
python -m pytest tests/test_api.py -v
```

浏览器手工验收清单（spec 06 §6 M2 条目）逐条通过，截图附在交付说明。

## M3 — 对抗生成器 + 竞技场 + 对抗/校准视图（2 个会话）

交付：`generator/`（spec 04 全部）、arena 支持 game_source=adversarial、UI 的 Generator 与 Calibration 两个 Tab（spec 06 §3§4）。

验收：

```bash
python -m pytest tests/test_generator.py -v
python -m arc3math.arena.cli --source adversarial --episodes 100 --seed 7
# 输出末尾打印: 前30局 overconf p50 vs 后30局 overconf p50（后者应更低）
```

UI：热力图/画廊/可靠性图有真实数据；高置信错误行可跳转回放。

## M4 — 仪表盘 + 课程闭环 + SFT 导出（1 个会话）

交付：Dashboard Tab（spec 06 §1）、指标齐全、`export_sft.py` + `/export/sft`、（加分）`carry_prior` 开关（spec 05 §5）。

验收：1000 局 adversarial run 全程无崩溃；`/export/sft` 产出的 JSONL 逐行通过 schema 校验脚本；仪表盘四条曲线趋势可见（solve_rate ↑、ECE ↓、overconf ↓、difficulty ↑）。

## M5（可选）— 真实 ARC-AGI-3 适配器

交付：`engine/remote_adapter.py` 实现 EnvAdapter（spec 02 §6），对接官方 API（实现前先查 three.arcprize.org / arcprize.org 最新文档；需要 API key，从环境变量 `ARC_API_KEY` 读）。agent 零改动打真实游戏，事件流照常入库，UI 照常回放（假设面板对真实游戏尤其有观赏价值）。

验收：对官方任意一个公开游戏完成 ≥1 局交互并在 UI 回放（不要求通关）。

## 里程碑喂给执行模型的固定开场白模板

```
你要实现 arc3-math 项目的 M{n}。先完整阅读 PLAN.md 与 specs/{相关文件}，
严格遵守 specs/07-milestones.md §0 执行守则。
本里程碑的交付物与验收标准见 specs/07-milestones.md 的 M{n} 小节。
完成后运行全部验收命令并原样贴出输出。
```
