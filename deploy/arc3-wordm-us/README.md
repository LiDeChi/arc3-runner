# arc3.wordm.us deployment

这是合并前 World Model 项目的 Cloudflare Worker 静态入口。为避免既有域名中断，
Worker 名称 `arc3-platform-agent` 和路由 `arc3.wordm.us/*` 保持不变。

部署前先确认已登录正确的 Cloudflare 账户，然后在本目录执行：

```bash
npx wrangler deploy
```

部署是显式运维操作，不属于本地 `make dev`。原始版本保存在
`archive/world-model-20260705`。
