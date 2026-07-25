# arc3-math

以"空间变换函数"为核心认知的 ARC-AGI-3 agent 训练系统：

- Agent 把每个动作理解为数学变换函数（上 = T(0,-1)，斜上按钮 = 被共轭/合成过的"上"），用贝叶斯程序归纳推断、用函数合成的心理模拟做想象规划；
- 对抗生成器专门合成"打破习以为常函数"的陷阱游戏，训练 agent 的可信度判断（校准）；
- 全流程事件化，配可视化界面：对局回放（含 agent 脑内假设与想象轨迹）、对抗热力图、校准曲线。

## 文档

- [PLAN.md](PLAN.md) — 总方案（理念、架构、里程碑）
- [specs/01-dsl.md](specs/01-dsl.md) — 变换 DSL
- [specs/02-engine.md](specs/02-engine.md) — 游戏引擎
- [specs/03-agent.md](specs/03-agent.md) — 数学思维 Agent
- [specs/04-generator.md](specs/04-generator.md) — 对抗生成器
- [specs/05-backend-api.md](specs/05-backend-api.md) — 后端与数据
- [specs/06-ui.md](specs/06-ui.md) — 可视化界面
- [specs/07-milestones.md](specs/07-milestones.md) — 里程碑与验收（从这里开始执行）

## 真实 ARC-AGI-3 游戏

本项目现在支持官方 ARC-AGI-3 REST API，区别于本地手写/合成 `GameSpec`：

```bash
export ARC_API_KEY="your-api-key"
cd backend
python3 -m arc3math.arena.cli \
  --source official \
  --game-id ls20-016295f7601e \
  --card-id d0c1c48f-5774-40c7-bb7d-9679df6aebb3 \
  --max-steps 10 \
  --out /tmp/official-trace.jsonl
```

如果不传 `--game-id`，系统会调用 `/api/games` 选择第一个可用官方游戏；如果不传 `--card-id`，系统会调用 `/api/scorecard/open` 创建一个 scorecard。UI 顶栏也提供 `Start Official` 入口，创建后仍用同一个 Episode Viewer 回放官方返回的真实 `frame`。
