# Spec 02 — 游戏引擎（engine/ 模块）

确定性网格游戏引擎。游戏完全由一份 GameSpec JSON 定义，动作语义直接绑定 DSL 程序（spec 01）。

## 1. GameSpec JSON schema

```json
{
  "id": "mirror-room-01",
  "size": {"w": 10, "h": 10},
  "tiles": [[0,0,1, ...], ...],        // h 行 w 列，tile 枚举见 §2
  "entities": [
    {"id": "agent", "kind": "agent", "x": 1, "y": 8, "color": 4}
  ],
  "actions": {
    "A1": {"program": { DSL程序 }, "hint": "arrow_up"},
    "A2": {"program": { ... }, "hint": "arrow_down"},
    "A3": {"program": { ... }, "hint": "arrow_left"},
    "A4": {"program": { ... }, "hint": "arrow_right"},
    "A5": {"program": { ... }, "hint": "star"}          // 可选
  },
  "regimes": [                          // 可选：非平稳动力学。actions 的覆盖档位
    {"actions": { "A1": {...} }}        // regime=1 时 A1 换语义，其余沿用档位0
  ],
  "win": {"type": "reach_goal"},        // 或 {"type":"collect_keys","n":2}
  "max_steps": 100,
  "meta": {
    "traps": ["conjugate_mirror"],      // 生成器写入的陷阱标签（手写游戏为 []）
    "difficulty": 3.5,
    "seed": 42
  }
}
```

- `hint` 只影响 UI 上按钮的**装饰图标**，与真实语义无关——这正是"诱饵图标"陷阱的载体。
- 动作枚举固定为 `RESET, A1..A5`（对齐 ARC-AGI-3 的语义无关按钮设定；A6 点击类动作留给 M5 扩展）。

## 2. Tile 枚举与调色板

| 值 | 名称 | 行为 |
|---|---|---|
| 0 | empty | 可通行 |
| 1 | wall | 阻挡（见 §3） |
| 2 | goal | 到达即胜（reach_goal） |
| 3 | lava | 进入即败 |
| 4 | switch | 进入时 regime = (regime+1) % len(regimes+1)，然后 tile 保持 |
| 5 | portal_a / 6 portal_b | 进入 a 传送到 b（双向） |
| 7 | key / 8 door | 踩 key 得钥匙（tile 变 0）；有钥匙可穿 door（消耗，door 变 0） |
| 9 | hint_decor | 纯装饰，可通行（诱饵箭头贴图放这里，方向存 meta） |

渲染调色板（前端常量，16 色对齐 ARC 风格，0-9 用经典 ARC 色）：
`#000000 #0074D9 #FF4136 #2ECC40 #FFDC00 #AAAAAA #F012BE #FF851B #7FDBFF #870C25 #4B0082 #2F4F4F #8B4513 #556B2F #C71585 #FFFFFF`

## 3. step() 语义（唯一权威定义）

```python
def step(spec: GameSpec, state: State, action: str) -> StepResult
# StepResult = {state, done: bool, result: "win"|"lose"|"timeout"|None}
```

顺序：

1. `RESET` → 返回初始状态。
2. 取当前 regime 下该动作的程序 prog（regime 覆盖表里没有的动作沿用档位 0）。
3. `intended = apply_program(prog, state)`（DSL 层，算意图状态）。
4. **裁决**（agent 作用域移动）：意图位置越界或为 wall / 无钥匙的 door → **整个移动取消**，agent 原地不动（外显行为 = identity，这天然构成"是墙还是假设错了？"的歧义，agent 必须自己分辨）。
5. 结算脚下 tile：lava→lose；portal→传送；key/door/switch 按 §2；goal→win（reach_goal 模式）。
6. `step_count += 1`；超过 max_steps → timeout（判负）。
7. world 作用域程序（如旋转地板）在裁决后应用，实体坐标随网格同步变换。

全程无随机性；任何随机（生成器用）必须来自显式传入的 seed。

## 4. 手写示例游戏（games/，M1 交付 5 个）

| 文件 | 设计 | 考察 |
|---|---|---|
| `g01_plain.json` | 4 方向正常，直达 goal | 基线：先验直接命中 |
| `g02_permuted.json` | A1..A4 映射被打乱（如 A1=左） | 映射置换的快速识别 |
| `g03_mirror.json` | 全部动作被 M_h 共轭（上下颠倒） | 共轭假设 |
| `g04_diagonal.json` | A1 = T(1,-1) 斜上，须配合 A3 修正 | 合成推理 + 想象规划 |
| `g05_region.json` | 左半场正常，右半场左右镜像（conditional in_region） | 分段函数 + 主动实验 |

每个游戏 10×10，均须附带 oracle 解（最短动作序列，写入 `games/solutions.json`），供引擎测试断言可解。

## 5. 测试要求（M1 验收的一部分）

- `tests/test_engine.py`：墙/门/钥匙/传送/switch/regime 各 ≥2 用例；5 个手写游戏按 oracle 解回放全部 win。
- 确定性测试：同一 spec+动作序列跑两遍，逐步状态完全一致。

## 6. EnvAdapter 接口（为 M5 对接真实 ARC-AGI-3 预留）

```python
class EnvAdapter(Protocol):
    def reset(self) -> Observation: ...          # Observation = {"grid": [[..]], "done": bool, "result": str|None}
    def step(self, action: str) -> Observation: ...
    def action_space(self) -> list[str]: ...
```

本地引擎实现该接口；M5 再写一个包装官方 REST API（three.arcprize.org，实现时查阅官方文档）的 RemoteAdapter。**agent 代码只依赖此接口**，不得直接 import 引擎内部。注意：真实 ARC-AGI-3 只给像素网格、不给实体列表，因此 agent 的观察输入必须是纯网格帧（实体由 agent 自己做帧间差分识别，见 spec 03 §2）。
