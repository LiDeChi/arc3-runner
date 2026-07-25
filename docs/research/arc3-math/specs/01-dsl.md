# Spec 01 — 变换 DSL（dsl/ 模块）

所有"动作的语义"都用这个 DSL 的程序表示。引擎用它定义真实动力学，agent 用它表示假设，生成器用它构造陷阱。**三方共用同一份解释器代码**，这是系统正确性的基石。

## 1. 坐标与状态约定

- 坐标：x = 列（向右 +），y = 行（向下 +）。网格存为 numpy int8 数组 `grid[y][x]`。
- "上" 的规范定义：T(0,-1)。
- 状态 State（Python dataclass，可 JSON 序列化）：

```json
{
  "grid": [[0,1,0], ...],          // 静态图块层，值为 tile 枚举（见 spec 02）
  "entities": [
    {"id": "agent", "kind": "agent", "x": 3, "y": 5, "color": 4},
    {"id": "box1", "kind": "box", "x": 1, "y": 2, "color": 8}
  ],
  "step_count": 12,
  "regime": 0,                      // 当前动力学档位（非平稳陷阱用）
  "flags": {}                       // 钥匙数等
}
```

## 2. 程序 AST（JSON schema，固定不可改）

程序是一棵 JSON 树，每个节点有 `op` 字段。两种作用域：

- **agent 作用域**（默认）：变换作用于 agent 实体的位置向量 (x,y)
- **world 作用域**：变换作用于整个网格（用于旋转地板等特殊机制），节点加 `"scope": "world"`

### 2.1 原语

| op | 参数 | 语义（agent 作用域） | MDL 成本 |
|---|---|---|---|
| `identity` | — | (x,y) → (x,y) | 1 |
| `translate` | dx, dy ∈ [-3,3] | (x,y) → (x+dx, y+dy) | 1 + 0.5·(‖(dx,dy)‖₁ − 1)，即单步平移成本 1，对角/长跳更贵 |
| `rotate` | k ∈ {1,2,3}（k×90° 顺时针，绕网格中心） | 位置向量绕中心旋转；world 作用域 = np.rot90 | 2 |
| `reflect` | axis ∈ {"h","v","d","a"}（水平轴/垂直轴/主对角/反对角） | 位置向量镜像；world 作用域 = np.flip / 转置 | 2 |
| `color_map` | map: {src: dst} | 仅 world 作用域：网格按映射换色 | 2 + 0.5·|map| |

### 2.2 组合子

| op | 参数 | 语义 | MDL 成本 |
|---|---|---|---|
| `compose` | fs: [f1, f2, ...] | 从左到右依次应用：先 f1 后 f2 | 0.5 + Σ成本(fi) |
| `conjugate` | g, f | g∘f∘g⁻¹。**v1 限定**：f 必须是 translate，g ∈ {rotate, reflect}。实现：有效平移向量 = 矩阵(g)·(dx,dy)，即共轭定律 g∘T(v)∘g⁻¹ = T(g·v) | 1.5 + 成本(g) + 成本(f) |
| `conditional` | pred, then, else | 谓词为真执行 then，否则 else | 2 + 成本(then) + 成本(else) + 成本(pred) |

### 2.3 谓词（conditional 用）

| pred | 参数 | 语义 | 成本 |
|---|---|---|---|
| `in_region` | x0,y0,x1,y1 | agent 在矩形内（含边界） | 1 |
| `agent_color` | c | agent 实体颜色 == c | 1 |
| `tile_under` | t | agent 脚下 tile == t | 1 |
| `step_mod` | k, r | step_count % k == r | 1.5 |
| `regime_is` | i | state.regime == i | 1 |

### 2.4 示例（本方案的三个招牌函数）

```json
// 普通的"上"
{"op": "translate", "dx": 0, "dy": -1}

// 镜像世界的"上"（实际向下）：M_h ∘ T(0,-1) ∘ M_h⁻¹ = T(0,+1)
{"op": "conjugate",
 "g": {"op": "reflect", "axis": "h"},
 "f": {"op": "translate", "dx": 0, "dy": -1}}

// 左半场正常、右半场镜像的"上"
{"op": "conditional",
 "pred": {"pred": "in_region", "x0": 0, "y0": 0, "x1": 4, "y1": 9},
 "then": {"op": "translate", "dx": 0, "dy": -1},
 "else": {"op": "translate", "dx": 0, "dy": 1}}
```

## 3. 解释器契约

```python
def apply_program(prog: dict, state: State) -> State: ...
```

- 纯函数：不修改输入，返回新 State。
- agent 作用域越界/撞墙的处理**不在 DSL 层**，由引擎层裁决（见 spec 02 §3）；DSL 只算"意图位置"。
- `conjugate` 在加载时即可**规范化**为等效 translate（矩阵乘出来），但 AST 原样保留用于展示（UI 要显示数学式）。
- 提供 `program_to_math(prog) -> str`：渲染为等宽数学记号，如 `M_h ∘ T(0,-1) ∘ M_h⁻¹`、`if in([0,0],[4,9]) then T(0,-1) else T(0,1)`。UI 直接用这个字符串。

## 4. MDL 与先验

- `mdl(prog) -> float` 按上表递归求和。
- 先验 `prior(prog) = exp(-mdl(prog))`，在假设集合内归一化。
- 这个先验就是"习以为常"的数学化：`T(0,-1)`（成本 1）远比它的共轭版本（成本 ≥4.5）可信——直到证据说话。

## 5. 程序枚举器

```python
def enumerate_programs(max_mdl: float = 8.0, scope: str = "agent") -> list[dict]
```

- 按 MDL 从小到大生成所有语法合法程序（迭代加深）。
- **外延去重**：在 16 个固定探针状态（不同位置/颜色/step_count 的 agent）上求值，行为完全相同的程序只保留 MDL 最小者。
- 约束：conditional 不嵌套 conditional（v1）；compose 长度 ≤ 3；数值参数按 §2.1 范围。
- 验收基准：max_mdl=8 时枚举数量在 200~5000 之间（确切数字以实现为准，写入 golden 文件锁定）。

## 6. 测试要求（M0 验收）

- `tests/test_dsl.py`：每个原语/组合子至少 3 个 golden 用例（输入状态 + 程序 + 期望输出，手算写死）。
- **共轭定律测试**：对所有 g ∈ {R1,R2,R3,M_h,M_v,M_d,M_a} × v ∈ 8 个单位/对角向量，验证 `apply(conjugate(g,T(v)))` ≡ `apply(T(matrix(g)·v))`。
- 枚举器测试：数量落在区间、无重复外延、MDL 单调。
