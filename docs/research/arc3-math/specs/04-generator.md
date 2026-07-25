# Spec 04 — 对抗游戏生成器（generator/ 模块）

目标不是"难"，是**高置信错误**：让 agent 在先验最自信的地方摔跤，从而学会可信度判断。无神经网络，模板 + 陷阱库 + UCB1 bandit，全部可复现（seed 驱动）。

## 1. 生成流水线

```
sample_template(seed) → sample_traps(bandit) → build_gamespec()
  → check_solvable() ✔ → check_identifiable() ✔ → 发布到竞技场
  （任一检查失败 → 丢弃并计数，重采样，最多重试 20 次）
```

## 2. 模板族（布局骨架）

| 模板 | 描述 |
|---|---|
| `corridor` | 走廊 + 转角，agent 在一端，goal 在另一端 |
| `two_rooms` | 两房间由门/传送门连接 |
| `maze_small` | 递归分割迷宫（seed 决定） |
| `open_field` | 空场 + 少量 lava 障碍 |
| `key_door` | 必须先取钥匙 |

模板参数：尺寸 8~16、墙密度、lava 数量，均由 seed 决定。

## 3. 陷阱库（核心资产，每个都是"对习以为常函数的攻击"）

| # | 名称 | 实现（改动 GameSpec 的方式） | 攻击的先验 |
|---|---|---|---|
| 1 | `permute` | A1..A4 的程序随机置换 | "按钮顺序=上下左右" |
| 2 | `conjugate_mirror` | 全部方向动作被 M_h 或 M_v 共轭 | "上就是 y−1" |
| 3 | `conjugate_rotate` | 全部方向动作被 R_k 共轭（整体转 90°/180°） | 同上 |
| 4 | `diagonal` | 1~2 个动作换成对角平移 T(±1,±1) | "移动是轴对齐的" |
| 5 | `region_split` | 方向动作变 conditional(in_region)：两半场语义不同 | "函数全局同一" |
| 6 | `color_state` | 语义依赖 agent_color（踩染色 tile 换色后操作反转） | "函数与自身状态无关" |
| 7 | `regime_switch` | regimes + switch tile：踩开关后全部映射置换 | "函数不随时间变" |
| 8 | `decoy_hint` | hint 图标与真实语义**故意相反**（arrow_up 配下移程序），并在地图铺 hint_decor 箭头 | "视觉提示可信" |
| 9 | `wall_ambiguity` | 在 agent 出生点周围布墙，使前几步高概率撞墙（外显 identity） | "没反应=动作无效"（其实只是被挡） |
| 10 | `long_jump` | 某动作是 T(0,-2) 或 T(2,0) 跳跃 | "一步移动一格" |

组合规则：一次抽 1~3 个陷阱（bandit 决定），互斥对：{2,3}（只取一）、{5,6,7}（至多一）。`meta.traps` 如实记录，供 UI 热力图。

## 4. 可解性检查 check_solvable

预言机（知道全部真实程序）在真实动力学上 BFS：`max_steps` 内可达 win → 通过。同时把 oracle 最短解长度记入 `meta.oracle_len`。

## 5. 可推断性检查 check_identifiable

保证"陷阱是可以被实验识破的谜题，不是噪声"：

- 对 oracle 解用到的每个动作 a：在 `enumerate_programs(max_mdl=8)` 中找出与真值程序**外延不等价**但在初始状态邻域（agent 初始可达的 ≤K=12 步状态集，用真实动力学展开）上预测始终一致的竞争假设；
- 若存在这种"K 步内不可分辨"的竞争假设，且该歧义会导致 BFS 计划差异 → 判不可推断，丢弃。
- 实现允许蒙特卡洛近似：采样 200 个可达状态验证分歧存在性。

## 6. UCB1 bandit（自动课程）

- **臂** = 陷阱组合（单陷阱 10 + 精选二元组合 ≈ 25 个臂，组合表写死在代码里）。
- **回报**（episode 结束后）：

```
r = 0.6·overconf + 0.4·fail
overconf = mean(conf_t · 1[预测错误_t])   # 高置信错误，主奖励
fail     = 1[agent 未通关]
```

- UCB1：`score_i = r̄_i + c·sqrt(ln N / n_i)`，c=1.2；每局选 score 最高的臂。
- **退火**：某臂连续 5 局 r̄ < 0.1（agent 已免疫）→ 权重衰减，bandit 自然转向新弱点。这就是"课程自动前进"。
- 每次臂选择与回报记 `generator_update` 事件（UI 对抗视图消费）。

## 7. 难度记分

`difficulty = Σ mdl(真值程序 − 基线程序) + 3·len(traps) + 2·1[有regimes]`，写入 meta，仪表盘画难度演化曲线。

## 8. 测试要求（M3 验收的一部分）

- 固定 seed 下：连续生成 50 个游戏全部通过双检查（允许内部重采样），且陷阱标签分布非退化（≥6 种陷阱出现过）。
- `check_solvable` 对故意堵死的 spec 返回 False（构造 2 个反例用例）。
- bandit 单测：喂入伪造回报序列，验证臂选择收敛到高回报臂。
- 与 agent 联测：跑 100 局竞技场，`overconf` 指标前 30 局均值 > 后 30 局均值（agent 确实被训练得更校准——统计断言允许宽松：用 p50 中位数比较）。
