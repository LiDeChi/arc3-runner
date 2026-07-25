---
name: arc3-run
description: ARC3 快速入口 — train / eval / export / dashboard 快捷命令
---

# arc3-run

ARC3 训练/评估/导出快速入口。项目根目录运行。

## 用法

`/arc3-run <command> [args...]`

| 命令 | 作用 |
|---|---|
| `train` | 启动对抗训练 |
| `eval` | 评估求解器 |
| `export` | 导出训练后的求解器 |
| `dashboard` | 启动监控面板 |

## 示例

```
/arc3-run train --rounds 50
/arc3-run eval --task some_task.json
/arc3-run eval --dir ./tasks/
/arc3-run export --output my_solver.py
/arc3-run dashboard
```

## 参数透传

所有参数原样透传给 `python3 -m arc3_trainer.cli`。

## 实现

```bash
cd /Users/lidechi/Documents/deepseek/arc3
python3 -m arc3_trainer.cli "$@"
```
