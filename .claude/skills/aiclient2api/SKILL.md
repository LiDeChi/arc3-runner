---
name: aiclient2api
description: "Start, stop, and use the local AIClient2API (A2) service. Use whenever the user asks to launch/start the AI proxy, get its status, access the Web UI, or configure AI clients/agents to use the unified OpenAI-compatible endpoint on this machine. Primary commands for startup and everyday operation."
argument-hint: "[start | status | stop | help | logs]"
user-invocable: true
---

# AIClient2API Local Service Skill (Global)

This skill lets any agent on this machine start, manage, and consume the AIClient2API proxy.

**Repository location (this machine):** `/Users/lidechi/Documents/Github/AIClient2API`

## 🚀 Start the Service (Startup Commands)

### Recommended (one-command)
```bash
cd /Users/lidechi/Documents/Github/AIClient2API
chmod +x install-and-run.sh
./install-and-run.sh
```

### Manual / Fast
```bash
cd /Users/lidechi/Documents/Github/AIClient2API
npm start
# or directly:
node src/core/master.js
```

### Other variants
- Dev mode (more logs): `npm run start:dev`
- Pure backend (no auto-open UI): `npm start -- --no-ui`
- With forced git pull first: `./install-and-run.sh --pull`

The server starts on **http://localhost:3000** (and 0.0.0.0:3000).

A management master process also listens on **port 3100**.

After start it automatically opens the login page in the default browser.

**Default admin password:** `admin123`
- Change it by editing the `pwd` file in the project root, or via the Web UI after login.

## ✅ Verify It Is Running

```bash
# Quick health
curl http://localhost:3000/health

# Port check
lsof -i :3000 -sTCP:LISTEN

# Master status
curl http://localhost:3100/master/status
```

Or visit in browser: http://localhost:3000

## 🛑 Stop / Restart

- Press **Ctrl+C** in the terminal running it (if foreground).
- Or kill the worker/master:
  ```bash
  pkill -f "node src/core/master.js" || pkill -f "api-server.js"
  ```
- Via master API (if running):
  ```bash
  curl -X POST http://localhost:3100/master/stop
  curl -X POST http://localhost:3100/master/start
  ```

## 📖 Usage Commands & Self-Discovery (for Agents & Humans)

When the service is running, use these to learn everything:

### Local Shell (best when you have terminal access)
```bash
cd /Users/lidechi/Documents/Github/AIClient2API

npm run help              # Full CLI help
npm run help -- --json    # Structured JSON help (preferred for agents)

npm run example:api              # API usage examples
npm run example:api -- --json    # JSON examples
```

### REST (works locally and remotely)
Public, no auth:
- `GET http://localhost:3000/api/help`          → complete API surface (JSON)
- `GET http://localhost:3000/api/example`       → ready-to-use examples
- `GET http://localhost:3000/provider_health`   → live health of all providers

After login for management:
1. `POST /api/login` with `{ "password": "admin123" }` → returns token
2. Use `Authorization: Bearer <token>` for `/api/*` endpoints (config, providers, logs, etc.)

## Common Agent Workflow

1. Ensure service is running (`aiclient2api start`).
2. Ask user (or read config) for the **API Key** used by client calls (see configs or UI).
3. Tell other tools/clients to point to:
   - Base URL: `http://localhost:3000/v1`
   - Auth: `Authorization: Bearer <the-api-key>`
4. For advanced routing prefix providers, e.g. `/grok-cli-oauth/v1/chat/completions`
5. Use `/api/help` or `npm run help -- --json` to discover new endpoints dynamically.

## Web UI
- Open http://localhost:3000
- Login with admin password
- Sections: Dashboard, Config, Providers, Logs, Playground, etc.
- Changes are usually live/hot-reloaded.

## Important Notes for All Agents

- **Always prefer local shell commands** (`npm run help`, direct `node`) when the agent is on the same machine as the service.
- The project root must be the working directory for npm scripts.
- Some providers (Grok, etc.) rely on the `tls-sidecar` binary — it is pre-built in `tls-sidecar/tls-sidecar`.
- Config lives in `configs/`. OAuth tokens, pools, custom models etc. are there.
- Logs: `logs/` directory + real-time SSE at `/api/events`.

## Quick Reference Table

| Goal                    | Command / URL                                      |
|-------------------------|----------------------------------------------------|
| Start (easiest)         | `./install-and-run.sh` (in project dir)            |
| Start (manual)          | `npm start`                                        |
| Help (text)             | `npm run help`                                     |
| Help (JSON for agents)  | `npm run help -- --json`                           |
| Examples                | `npm run example:api`                              |
| Service health          | `curl http://localhost:3000/health`                |
| Full API docs           | `curl http://localhost:3000/api/help`              |
| UI                      | http://localhost:3000                              |
| Stop                    | Ctrl+C or `pkill -f api-server.js`                 |

This skill makes AIClient2API startup and operation first-class and available to **every agent** on the machine via the central skill system.
