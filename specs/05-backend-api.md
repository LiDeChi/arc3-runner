# Spec 05 — 后端服务与数据（arena/ + api/ 模块）

一切训练过程都落成**结构化事件流**，UI 完全靠事件回放重建现场。这是"直观清晰看到训练全流程"的技术保证。

## 1. SQLite schema（backend/arc3math/arena/db.py，标准库 sqlite3）

```sql
CREATE TABLE runs (
  id TEXT PRIMARY KEY,              -- uuid
  config_json TEXT NOT NULL,        -- RunConfig 全量
  status TEXT NOT NULL,             -- running|paused|done
  created_at TEXT NOT NULL
);
CREATE TABLE games (
  id TEXT PRIMARY KEY, run_id TEXT,
  spec_json TEXT NOT NULL,          -- 完整 GameSpec
  traps_json TEXT NOT NULL, difficulty REAL, oracle_len INTEGER
);
CREATE TABLE episodes (
  id TEXT PRIMARY KEY, run_id TEXT, game_id TEXT,
  idx INTEGER,                      -- run 内序号
  result TEXT,                      -- win|lose|timeout
  steps INTEGER, avg_conf REAL, overconf REAL,
  probe_steps INTEGER, revisions INTEGER,
  created_at TEXT
);
CREATE TABLE events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  episode_id TEXT, step_idx INTEGER,
  type TEXT NOT NULL, payload_json TEXT NOT NULL
);
CREATE TABLE metrics (
  run_id TEXT, episode_idx INTEGER, name TEXT, value REAL,
  PRIMARY KEY (run_id, episode_idx, name)
);
```

## 2. 事件类型（payload schema 固定；UI 契约）

| type | payload 关键字段 |
|---|---|
| `episode_start` | game_id, spec（全量，UI 画图 & 显示按钮 hint 图标） |
| `observation` | grid, entities?, step_idx |
| `hypotheses` | 每个动作的 top3：`{action, items:[{program, math, prob}]}`（math = program_to_math 字符串） |
| `plan` | intent(goal/probe), actions[], imagined_grids[]（想象帧）, risk |
| `prediction` | action, predicted_grid, conf |
| `action_taken` | action, intent |
| `outcome` | actual_grid, match_ratio, surprise, correct(bool) |
| `belief_revision` | action, old_top(math), new_candidates_count, trigger(collapse/nonstationary) |
| `episode_end` | result, steps, avg_conf, overconf, probe_steps, revisions |
| `generator_update` | arm(陷阱组合), reward, ucb_scores{arm: score} |

Agent 的 Trace.log 直接产出这些事件；arena 负责落库 + WS 广播。**每步的事件顺序固定**：hypotheses → plan → prediction → action_taken → observation(新) → outcome → (belief_revision?)。

## 3. REST API（FastAPI，前缀 /api）

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/runs` | body=RunConfig（episodes 数、seed、agent cfg、generator cfg、game_source: "handwritten"\|"adversarial"），后台线程启动竞技场循环，返回 run_id |
| POST | `/runs/{id}/pause` · `/resume` | 训练循环在每局边界检查暂停标志 |
| GET | `/runs` / `/runs/{id}` | 列表 / 详情+最新指标 |
| GET | `/runs/{id}/episodes?limit&offset` | episode 摘要列表 |
| GET | `/episodes/{id}/events` | 该局全部事件（回放数据源，按 step_idx 排序） |
| GET | `/runs/{id}/metrics?names=ece,solve_rate` | 时间序列（按 episode_idx） |
| GET | `/runs/{id}/calibration` | 可靠性图数据：10 个 bin 的 (mean_conf, accuracy, count) + 高置信错误事件定位列表 [{episode_id, step_idx, conf}] |
| GET | `/runs/{id}/traps` | 陷阱热力图数据：每陷阱组合 {plays, agent_win_rate, overconf_mean, ucb} |
| POST | `/games/preview` | body=generator 参数+seed → 返回一个 GameSpec（不入库），UI 预览合成游戏 |
| GET | `/export/sft?run_id=` | JSONL 下载（spec 03 §7） |

## 4. WebSocket

`WS /api/ws/runs/{run_id}`：服务器把该 run 的每个事件实时推送（与落库同一份 JSON，外层包 `{episode_id, step_idx, type, payload}`）。心跳 30s。前端断线重连后用 REST 补拉缺口（以最后收到的 event id 为游标，`GET /episodes/{id}/events?after_id=`）。

## 5. 竞技场循环（arena/loop.py）

```python
def arena_loop(run_cfg):
    bandit = Bandit(...); agent_cfg = ...
    for i in range(run_cfg.episodes):
        wait_if_paused()
        game = pick_handwritten(i) if run_cfg.game_source=="handwritten" \
               else generate(bandit, seed=run_cfg.seed+i)      # spec 04
        trace = run_episode(LocalEnv(game), agent_cfg)          # spec 03
        persist(trace); broadcast(trace)
        if run_cfg.game_source=="adversarial":
            bandit.update(arm, reward(trace))                   # spec 04 §6
        write_metrics(i, trace)   # solve_rate滑窗20, ece滑窗200步, overconf, probe_steps, difficulty
```

**注意**：agent 的假设后验默认**跨局重置**（每局都是新游戏），但校准统计、bandit、指标是跨局累积的——"训练"的对象是这套系统的课程与评估，v1 的 agent 本身无参数。（保留 `cfg.carry_prior=True` 开关：把上一局验证过的陷阱结构作为先验注入枚举器成本折扣，作为 M4 的加分项。）

## 6. 运行方式

- `make dev-api` → `uvicorn arc3math.api.main:app --reload --port 8321`
- `make arena` → CLI 直接跑一个 run（无 UI 场景），参数 `--episodes --source --seed`
- CORS 放开 localhost:5173（Vite 默认端口）

## 7. 测试要求（M2/M3 验收的一部分）

- `tests/test_api.py`（fastapi TestClient）：建 run → 跑 3 局手写游戏 → episodes/events/metrics 各端点返回符合 schema；事件顺序断言（§2 的固定顺序）。
- WS 冒烟测试：收到 ≥1 条 `episode_start` 与 `episode_end`。
