---
name: enable-cliproxyapi-codex-oauth
description: 安全检测、配置并启用本机 router-for-me/CLIProxyAPI，使用 Codex OAuth 提供本地 OpenAI 兼容接口。用于用户要求启用、修复或验证已安装的 CLIProxyAPI，复用同一 ChatGPT/Codex 账户完成 OAuth 授权，查找活动配置，限制服务仅监听回环地址，配置本地 API key，关闭远程管理，启动或重启服务，验证 /v1/models、Responses 或 Chat Completions，以及排查 OAuth、端口、模型和鉴权故障时。
---

# 安全启用 CLIProxyAPI 的 Codex OAuth

## 适用场景与边界

将 CLIProxyAPI 作为单用户、本机开发用 sidecar。仅在用户拥有该 Codex/ChatGPT 账户、CLIProxyAPI 已获准进入任务范围且用途为本机调用时执行。不要把订阅凭据转成公开服务，不要建立共享账号池，不要把端口或管理面板暴露到局域网或公网。

区分两种“复用”：

- 允许复用同一 ChatGPT/Codex 账户及浏览器登录状态，再执行 CLIProxyAPI 自己的 OAuth 流程。
- 不要声称 CLIProxyAPI 会自动读取 Codex CLI 的 `~/.codex/auth.json`。当前官方登录流程会在配置的 `auth-dir` 中创建独立凭据记录。
- 不要复制、解析、转换、上传、打印或粘贴 `~/.codex/auth.json` 及 `auth-dir` 内任何 OAuth JSON。除非上游以后正式提供受支持的导入命令，否则不要自行转换 token 格式。

## 强制安全规则

在所有步骤中遵守以下规则：

1. 只检查 OAuth 文件是否存在、文件数量、所有者和权限；不要读取内容或输出文件名，因为文件名可能含邮箱。
2. 不要在命令行参数、聊天、日志或工具输出中放入 API key、access token、refresh token、ID token、授权码或完整 OAuth 回调 URL。
3. 禁用 shell xtrace：处理密钥前执行 `set +x`。从权限为 `0600` 的文件或隐藏输入读取本地 API key，使用后立即 `unset`。
4. 修改配置前创建权限为 `0600` 的时间戳备份。保留所有无关配置，不要用最小示例覆盖完整配置。
5. 只绑定 `127.0.0.1`；保持 `remote-management.allow-remote: false`，并将 `remote-management.secret-key` 留空以禁用 Management API。不要设置 `MANAGEMENT_PASSWORD`。
6. 不要杀死占用端口的未知进程，不要删除现有 OAuth 文件，不要轮换用户已有密钥，除非用户明确授权。
7. 只向 `http://127.0.0.1` 发验证请求。除非用户明确扩大范围，不要测试远程地址。

## 前置条件

确认当前用户能够读取活动配置并管理当前用户级服务。要求：

- CLIProxyAPI 二进制，常见名称为 `cliproxyapi`、`cli-proxy-api` 或 `CLIProxyAPI`。
- `python3` 和 `curl`；辅助脚本本身只依赖 Python 标准库。
- 可用浏览器；无浏览器时使用 `-no-browser` 或设备码流程。
- OAuth 回调端口可用。Codex 浏览器流程默认使用本机 TCP `1455`。
- 用户已登录或可登录其本人的 ChatGPT/Codex 账户。

将当前 Skill 根目录解析为 `SKILL_DIR`。不要假定 Skill 一定安装在 `~/.codex/skills`；执行资源时使用实际加载此 `SKILL.md` 的目录。

## 工作流

### 1. 只读检测安装、运行状态和配置

先执行脱敏检测：

```bash
python3 "$SKILL_DIR/scripts/inspect.py"
```

用户已给出配置路径时显式传入：

```bash
python3 "$SKILL_DIR/scripts/inspect.py" --config "/absolute/path/to/config.yaml"
```

优先级依次为：用户显式路径、运行进程的 `-config/--config` 参数、二进制帮助中的默认路径、包管理器默认路径、常见用户配置路径。不要在整个主目录中无界搜索。

记录但不要泄露以下事实：二进制路径与版本、活动配置路径、服务管理方式、监听地址、配置权限、`auth-dir`、OAuth JSON 数量、API key 数量及是否仍含模板值。不得输出 API key 或 OAuth 文件名。

如果发现多个实例或多个配置，先确定监听目标端口的进程实际使用哪个配置。配置不确定会显著改变结果时，停止写入并向用户说明候选路径。

### 2. 准备最小安全配置

目标配置至少满足：

```yaml
host: "127.0.0.1"
port: 8317

tls:
  enable: false

remote-management:
  allow-remote: false
  secret-key: ""
  disable-control-panel: true

auth-dir: "~/.cli-proxy-api"

api-keys:
  - "<至少 32 字节随机生成的本地客户端密钥>"

debug: false
ws-auth: true
```

这是必要字段片段，不是完整配置模板。保留现有 TLS、代理、路由、模型别名及其他无关设置；如果现有 TLS 已正确配置，不要为套用示例而关闭它。回环 HTTP 场景允许 `tls.enable: false`。

优先使用附带脚本做保守补丁。先预检，不写文件：

```bash
python3 "$SKILL_DIR/scripts/harden_config.py" --config "$CONFIG"
```

用户要求实际启用或修复时再应用：

```bash
python3 "$SKILL_DIR/scripts/harden_config.py" --config "$CONFIG" --apply
```

脚本应只改安全相关字段，移除 `your-api-key-1/2/3` 模板值，保留已有非模板 API key，并在 `auth-dir/client-api-key` 创建或复用一个权限为 `0600` 的本地密钥。脚本只报告路径和计数，不输出密钥。它同时把配置权限设为 `0600`、`auth-dir` 设为 `0700`、已有 OAuth JSON 设为 `0600`。

若配置结构无法被脚本安全识别，脚本必须拒绝修改；改为用 `apply_patch` 做最小人工补丁并复核差异，仍不得把密钥值显示在补丁或输出中。

### 3. 完成 CLIProxyAPI 自己的 Codex OAuth

确认二进制帮助实际支持登录参数：

```bash
"$BIN" -help 2>&1 | grep -E -- 'codex-(device-)?login|no-browser|config'
```

在交互终端中运行，并始终传入已确认的活动配置：

```bash
"$BIN" -codex-login -config "$CONFIG"
```

Go flag 通常接受单横线和双横线，但以本机 `-help` 输出为准。浏览器打开后选择用户自己的现有 ChatGPT/Codex 账户。浏览器会话可能减少重新输入登录信息，但这仍是一次新的 CLIProxyAPI OAuth 授权，不是复制 Codex CLI 凭据。

浏览器不能自动打开时执行：

```bash
"$BIN" -codex-login -no-browser -config "$CONFIG"
```

终端显示的授权 URL、授权码和完整回调 URL均视为敏感信息；让用户自行在本机操作，不要复制进聊天或工具输出。浏览器回调不可用但版本支持设备码时，改用：

```bash
"$BIN" -codex-device-login -config "$CONFIG"
```

登录后只比较 `auth-dir` 中 JSON 文件数量是否增加，不读取内容或列出文件名。然后收紧权限：

```bash
chmod 700 "$AUTH_DIR"
find "$AUTH_DIR" -type f -name '*.json' -exec chmod 600 {} +
```

### 4. 启动或重启正确实例

优先沿用检测到的现有服务管理方式：

```bash
# macOS Homebrew
brew services restart cliproxyapi

# Linux 用户级 systemd；服务名以检测结果为准
systemctl --user restart cli-proxy-api

# 前台运行；用于非服务安装
"$BIN" -config "$CONFIG"
```

容器安装只重启已确认挂载同一配置和 `auth-dir` 的容器。不要另起一个抢占相同端口的实例。

虽然 CLIProxyAPI 会监视配置和 `auth-dir` 并热加载，修改绑定地址后仍应重启，确保旧的通配监听套接字已经释放。随后重新运行 `inspect.py`，确认只出现 `127.0.0.1:<port>` 或等价的回环监听，不得出现 `*:<port>`、`0.0.0.0:<port>` 或 `[::]:<port>`。

### 5. 验证模型列表和一次推理调用

优先使用脱敏验证脚本。它从密钥文件或环境变量读取 API key，不打印请求头，只访问回环地址：

```bash
python3 "$SKILL_DIR/scripts/verify.py" \
  --base-url "http://127.0.0.1:${PORT:-8317}/v1" \
  --api-key-file "$AUTH_DIR/client-api-key" \
  --mode responses
```

这会先验证 `GET /v1/models`，自动选择 `owned_by=openai` 的模型，再验证一次 `POST /v1/responses`。如目标客户端只使用 Chat Completions，改为：

```bash
python3 "$SKILL_DIR/scripts/verify.py" \
  --base-url "http://127.0.0.1:${PORT:-8317}/v1" \
  --api-key-file "$AUTH_DIR/client-api-key" \
  --mode chat
```

已有 API key 不在密钥文件中时，不要把密钥写进命令历史。使用隐藏输入：

```bash
set +x
IFS= read -r -s CLIPROXYAPI_API_KEY
export CLIPROXYAPI_API_KEY
python3 "$SKILL_DIR/scripts/verify.py" --mode responses
unset CLIPROXYAPI_API_KEY
```

需要手动验证时使用变量，不使用字面密钥：

```bash
set +x
IFS= read -r API_KEY < "$AUTH_DIR/client-api-key"
curl --fail-with-body --silent --show-error \
  -H "Authorization: Bearer $API_KEY" \
  "http://127.0.0.1:${PORT:-8317}/v1/models"

curl --fail-with-body --silent --show-error \
  -H "Authorization: Bearer $API_KEY" \
  -H 'Content-Type: application/json' \
  -d "{\"model\":\"$MODEL\",\"input\":\"只回复 OK\",\"stream\":false}" \
  "http://127.0.0.1:${PORT:-8317}/v1/responses"
unset API_KEY
```

`MODEL` 必须来自刚取得的 `/v1/models`，不要硬编码可能过期的模型名。成功标准是两个请求均返回 2xx，模型列表至少包含一个 OpenAI/Codex 模型，推理响应包含正常文本且不含鉴权错误。

## 常见故障排查

### 找不到二进制

检查 `command -v cliproxyapi`、`command -v cli-proxy-api` 和包管理器清单。Homebrew 常用命令名是 `cliproxyapi`，源码构建常见名称是 `cli-proxy-api`。不要仅凭仓库名推断命令名。

### 服务读取了错误配置

检查进程参数、LaunchAgent/systemd unit 和二进制 `-help` 的默认路径。Homebrew 服务通常读取 `$(brew --prefix)/etc/cliproxyapi.conf`，不一定读取 `~/.cli-proxy-api/config.yaml`。登录和启动必须显式使用同一个 `CONFIG`。

### `/v1/models` 返回 403 `unsafe_example_api_key`

配置仍含 `your-api-key-1`、`your-api-key-2` 或 `your-api-key-3`。运行 `harden_config.py --apply` 或做等价的脱敏最小补丁，重启后再试。不要把模板值当作可用密钥。

### 返回 401/403 鉴权错误

确认客户端使用的是顶层 `api-keys` 中的本地客户端密钥，而不是 OAuth access token、管理密钥或 OpenAI API key。确认 `Authorization` 格式为 `Bearer <local-api-key>`，但不要输出头部。

### OAuth 登录失败或模型列表为空

确认登录命令传入活动 `CONFIG`，并只检查该配置的 `auth-dir` 中 JSON 数量。若数量未增加，重新运行登录流程。若增加但模型为空，重启服务并检查脱敏日志中的 provider/refresh 错误；不要打印 token JSON。

### 回调端口 1455 被占用

用 `lsof -nP -iTCP:1455 -sTCP:LISTEN` 识别所有者。不要自动终止未知进程。可关闭已知冲突程序，或在本机版本支持时使用 `-oauth-callback-port <free-port>`；注意某些版本的上游重定向 URI可能仍固定为 1455，失败时优先使用设备码流程。

### 登录后文件权限为 0644 或目录为 0755

立即执行 `chmod 700 "$AUTH_DIR"` 和针对 JSON 的 `chmod 600`，再复查数量与权限。不要列出包含邮箱的文件名。

### 修改 `host` 后仍监听所有接口

确认修改的是活动配置，执行完整服务重启，再检查监听地址。若仍为通配地址，检查是否存在第二个实例、容器端口映射或服务参数覆盖。

### 429、配额耗尽或 5xx

429 通常是账户配额或冷却，不要通过增加账户、轮询账号池或规避限额来处理。5xx 先确认上游可用性和 CLIProxyAPI 版本，再分别试 Responses 与 Chat Completions；只截取已脱敏的错误类别、HTTP 状态和 request ID。

## 验收与汇报

完成时逐项确认：

- 已识别实际二进制、版本、活动配置和服务管理方式。
- 活动监听仅在回环地址。
- 顶层 API key 不为空且不含模板值；远程管理关闭。
- `auth-dir` 为 `0700`，OAuth JSON 为 `0600`。
- CLIProxyAPI 的 Codex OAuth 记录存在，但从未读取或输出内容。
- `/v1/models` 与一次 Responses 或 Chat Completions 调用均成功。
- 输出只包含路径、计数、权限、HTTP 状态、模型 ID 和简短响应；不包含任何密钥、token、邮箱或完整 OAuth URL。

如果只完成检测而未获授权修改，明确区分“已确认事实”“尚未执行的变更”和“下一步命令”。

## 上游依据

遇到版本差异时，以本机 `-help` 和当前官方文档为准：

- `https://help.router-for.me/introduction/quick-start`
- `https://help.router-for.me/configuration/provider/codex`
- `https://help.router-for.me/configuration/options`
- `https://github.com/router-for-me/CLIProxyAPI`
