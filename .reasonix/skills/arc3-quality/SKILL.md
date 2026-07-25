---
name: arc3-quality
description: ARC3 全流程质量检查 — ruff lint + format 检查 + mypy + pytest（可加 --fix 自动修复）
---

# arc3-quality

ARC3 全流程质量检查管道。在项目根目录运行。

按顺序执行：
1. ruff lint 检查
2. ruff format 格式检查
3. mypy 类型检查
4. pytest 全部测试

## 用法

| 参数 | 作用 |
|---|---|
| (无) | 完整检查管道（不修复） |
| `--fix` | 自动修复 lint + format 问题 |
| `--skip-test` | 跳过测试（只做 lint/format/typecheck） |
| `--skip-type` | 跳过 mypy（只做 lint/format/test） |
| `--quick` | 只做 ruff lint + format（最快反馈） |

## 示例

```
/arc3-quality                     # 完整管道
/arc3-quality --fix               # 自动修复 + 检查
/arc3-quality --quick             # 快速反馈（仅 ruff）
/arc3-quality --skip-test         # 不跑测试
```

## 实现

```bash
cd /Users/lidechi/Documents/deepseek/arc3

FIX=false
SKIP_TEST=false
SKIP_TYPE=false
QUICK=false

for arg in "$@"; do
  case "$arg" in
    --fix) FIX=true ;;
    --skip-test) SKIP_TEST=true ;;
    --skip-type) SKIP_TYPE=true ;;
    --quick) QUICK=true ;;
  esac
done

echo "=== ruff lint ==="
if [ "$FIX" = true ]; then
  python3 -m ruff check --fix arc3_trainer/ || true
else
  python3 -m ruff check arc3_trainer/ || true
fi
echo ""

echo "=== ruff format ==="
if [ "$FIX" = true ]; then
  python3 -m ruff format arc3_trainer/ || true
else
  python3 -m ruff format --check arc3_trainer/ || true
fi
echo ""

if [ "$QUICK" = true ]; then
  echo "Quick mode — done."
  exit 0
fi

if [ "$SKIP_TYPE" = false ]; then
  echo "=== mypy ==="
  python3 -m mypy arc3_trainer/ || true
  echo ""
fi

if [ "$SKIP_TEST" = false ]; then
  echo "=== pytest ==="
  python3 -m pytest arc3_trainer/tests/ -v --tb=short || true
  echo ""
fi

echo "=== quality check complete ==="
```
