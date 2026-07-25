# ARC3 Math Core

这是从原 `arc3-math` 项目抽出的本地数学推理核心，保留：

- 空间变换 DSL、MDL 枚举与函数合成；
- 本地 GameSpec 引擎和 oracle 搜索；
- 贝叶斯式动作假设、校准与 episode 事件；
- 对抗题生成器；
- SQLite 记录与 SFT 导出。

独立 FastAPI、前端和官方远程适配器没有重复并入；统一产品入口由仓库根目录的
`server/` 与 `web/` 提供。完整旧实现保存在 Git 分支
`archive/arc3-math-20260708`。

验证：

```bash
cd packages/arc3-math
python -m pytest -q
```

原始研究规格位于 `../../docs/research/arc3-math/`。
