---
name: arc3-test
description: ARC3 项目专用测试运行器 — 按模块、覆盖率、详细度运行测试
---

# arc3-test

ARC3 项目专用测试运行器。项目根目录下运行。

## 用法

通过 `run_skill` 或 `/arc3-test` 调用，传入参数：

| 参数 | 作用 |
|---|---|
| (无) | 运行全部测试 |
| `--module <name>` | 仅运行指定模块: cognitive / agent / generator / trainer / edge_cases |
| `--coverage` | 带覆盖率报告运行 |
| `--verbose` 或 `-v` | 详细输出 |
| `--file <path>` | 运行单个测试文件 |
| `-- <pytest_args>` | 透传其余参数给 pytest |

## 示例

```
/arc3-test                    # 全部测试
/arc3-test --module agent     # 仅 agent 测试
/arc3-test --coverage         # 带覆盖率
/arc3-test --file arc3_trainer/tests/test_cognitive.py -v  # 指定文件详细输出
```

## 模块名 → 文件映射

- cognitive → test_cognitive.py
- agent → test_agent.py
- generator → test_generator.py
- trainer → test_trainer.py
- edge_cases → test_edge_cases.py

## 实现

```bash
cd /Users/lidechi/Documents/deepseek/arc3

# Parse arguments
ARGS=()
COVERAGE=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --module)
      shift
      case "$1" in
        cognitive) ARGS+=(arc3_trainer/tests/test_cognitive.py) ;;
        agent)     ARGS+=(arc3_trainer/tests/test_agent.py) ;;
        generator) ARGS+=(arc3_trainer/tests/test_generator.py) ;;
        trainer)   ARGS+=(arc3_trainer/tests/test_trainer.py) ;;
        edge_cases) ARGS+=(arc3_trainer/tests/test_edge_cases.py) ;;
        *)         ARGS+=("arc3_trainer/tests/test_$1*.py") ;;
      esac
      ;;
    --coverage) COVERAGE=true ;;
    --file) shift; ARGS+=("$1") ;;
    --verbose|-v) ARGS+=(-v) ;;
    *) ARGS+=("$1") ;;
  esac
  shift
done

if [ ${#ARGS[@]} -eq 0 ]; then
  ARGS+=(arc3_trainer/tests/)
fi

if [ "$COVERAGE" = true ]; then
  python3 -m pytest "${ARGS[@]}" --cov=arc3_trainer --cov-report=term --cov-report=html
else
  python3 -m pytest "${ARGS[@]}"
fi
```
