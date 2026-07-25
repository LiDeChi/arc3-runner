# 🏋️ ARC3 对抗式训练平台

> 一个面向 ARC（Abstraction & Reasoning Corpus）挑战赛的智能训练平台。**平台本身就是一个智能体（Agent）**——它通过对抗生成的方式，不断创造越来越多样化和针对参赛者弱点的合成游戏，推动参赛智能体持续进化。

## 设计思想

传统的 ARC 解题器在静态数据集上训练，泛化能力有限。本平台的核心创新在于：

1. **对抗生成**：平台分析参赛智能体的能力画像（CapabilityProfile），自动识别其薄弱环节，然后针对性生成合成游戏进行强化训练。
2. **认知框架**：合成游戏和参赛智能体共享同一套认知框架，参考人类认知经验建立，包含：
   - **行动-差异感知**（Action-DiffPerception）：感知行动前后的差异，从中学习规律
   - **想象与预测**：通过行动组合（Compose）和控制流（Repeat/Conditional）进行预测
3. **课程化训练**：分阶段推进——从单原子动作到组合，再到控制流，最后进入对抗阶段。

## 快速开始

```bash
# 查看帮助
python3 -m arc3_trainer.cli --help

# 启动对抗式训练（100 轮）
python3 -m arc3_trainer.cli train --rounds 100 --output-dir ./training_output

# 评估解题器
python3 -m arc3_trainer.cli eval --task task.json
python3 -m arc3_trainer.cli eval --dir ./tasks/

# 启动 Web 仪表盘
python3 -m arc3_trainer.cli dashboard --port 8080

# 导出训练好的解题器
python3 -m arc3_trainer.cli export --output solver.py

# 运行测试
python3 -m pytest arc3_trainer/tests/
```

### CLI 选项

| 子命令 | 选项 | 默认值 | 说明 |
|---|---|---|---|
| `train` | `--rounds` | 100 | 训练轮数 |
| | `--beam-width` | 50 | 束搜索宽度 |
| | `--max-depth` | 5 | 最大程序深度 |
| | `--output-dir` | `training_output` | 输出目录 |
| | `--seed` | — | 随机种子 |
| `eval` | `--task` | — | 单任务 JSON 文件 |
| | `--dir` | — | 任务 JSON 目录 |
| | `--beam-width` | 50 | 束搜索宽度 |
| | `--max-depth` | 5 | 最大程序深度 |
| `dashboard` | `--host` | `127.0.0.1` | 绑定地址 |
| | `--port` | 8080 | 绑定端口 |
| `export` | `--output` | `exported_solver.py` | 输出路径 |

## 项目结构

```
arc3_trainer/
├── cli.py               # CLI 入口（argparse）
├── cognitive/            # 核心认知框架
│   ├── grid.py           # Grid：不可变 2D 网格（0-9 整数矩阵）
│   ├── actions.py        # Action DSL：原子/组合变换（旋转、翻转、染色等）
│   ├── diff.py           # DiffPerception：差异感知
│   ├── predictor.py      # Predictor：预测器
│   └── task_io.py        # 任务序列化/反序列化
├── agent/                # 参赛智能体
│   ├── perceiver.py      # 从训练对中提取约束
│   ├── hypothesizer.py   # 生成候选动作假设
│   ├── searcher.py       # 束搜索 + MDL 代价评估
│   └── solver.py         # 统一入口（感知 → 假设 → 搜索 → 求解）
├── generator/            # 合成游戏生成器
│   ├── grid_gen.py       # 网格生成器
│   ├── program_sampler.py # 程序采样器（支持加权偏置）
│   ├── task_packer.py    # 任务打包成输入/输出对
│   └── difficulty.py     # 难度控制
├── trainer/              # 对抗训练引擎
│   ├── loop.py           # TrainingLoop：主训练循环
│   ├── curriculum.py     # 课程调度器（4 阶段）
│   ├── capability.py     # 能力画像（动作×难度矩阵）
│   ├── weakness.py       # 弱点分析器
│   └── adversarial.py    # 对抗采样器
├── eval/                 # 评估模块
│   └── evaluator.py      # 标准 ARC 任务评估
├── dashboard/            # Web 仪表盘
│   ├── server.py         # FastAPI 服务器
│   ├── events.py         # SSE 事件总线
│   └── static/           # 前端（HTML/CSS/JS）
└── tests/                # 单元测试
    ├── test_agent.py
    ├── test_cognitive.py
    ├── test_edge_cases.py
    ├── test_generator.py
    └── test_trainer.py
```

## 架构概览

### 数据流

```
Generator ──→ Task ──→ Agent(Solver) ──→ Result
                    ↑                          │
                    │                          ↓
               Curriculum            CapabilityProfile
                                         │
                                         ↓
                                  WeaknessAnalyzer
                                         │
                                         ↓
                              AdversarialSampler ──→ Generator
```

### 认知框架（`cognitive/`）

Grid 是核心数据结构——不可变的 2D 整数矩阵（0-9），尺寸限制 1×1 到 30×30。

Action DSL 定义了四类变换：

| 类别 | 动作 |
|---|---|
| **几何** | 旋转（CW/CCW/180°）、翻转（H/V）、平移 |
| **着色** | 重染色、矩形填充、泛洪填充 |
| **结构** | 裁剪、扩展、区域复制、覆盖 |
| **控制** | Compose（组合）、Repeat（重复）、Conditional（条件） |

每个动作都有**基础复杂度代价**（MDL cost），引导搜索趋向更简单的程序。

### 对抗训练循环（`trainer/`）

训练分为 4 个阶段：

| 阶段 | 内容 | 难度 |
|---|---|---|
| S1 | 单个原子动作 | 1-2 |
| S2 | 2-3 个原始动作组合 | 2-4 |
| S3 | 控制流（repeat/conditional） | 4-7 |
| S4 | 对抗（针对性攻击弱点） | 5-8 |

每个阶段有通过条件（pass condition），达标后自动进入下一阶段。

### 仪表盘（`dashboard/`）

FastAPI 驱动的实时仪表盘，使用 SSE（Server-Sent Events）推送训练进度。前端支持：

- 启动/停止训练
- 实时查看训练轮次、阶段、成功率
- 查看能力画像和弱点分析

## 技术栈

- **Python 3.14+**（使用 `from __future__ import annotations`）
- **numpy**（Grid 底层存储）
- **FastAPI**（仪表盘后端）
- 无 pyproject.toml / requirements.txt——依赖由外部管理

## 代码约定

- 所有文件以 `from __future__ import annotations` 开头
- 完整类型注解，使用 `typing` 模块（`Optional`, `List`, `Dict` 等）
- Grid 不可变，所有变换返回新实例
- 使用 `logging.getLogger(__name__)`，不用 print
- 测试使用 `unittest.TestCase`，命名模式 `test_<单元>_<场景>`
- dataclass 用于结构化数据

## 训练输出示例

运行 `train` 后，输出目录包含：

```
training_output/
├── history_final.jsonl   # 训练历史（每轮一行 JSON）
└── profile_final.json    # 最终能力画像
```

## 许可证

（待定）
