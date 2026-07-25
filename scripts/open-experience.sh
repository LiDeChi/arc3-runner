#!/usr/bin/env bash
set -euo pipefail

if [[ -n "${CODEX_WORKTREE_PATH:-}" ]]; then
  project_root="$CODEX_WORKTREE_PATH"
else
  project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fi

api_port=8010
web_port=5174
api_url="http://127.0.0.1:$api_port"
web_url="http://127.0.0.1:$web_port"
runtime_dir="$project_root/.codex/run"
mkdir -p "$runtime_dir"

api_ready() {
  curl --silent --fail --max-time 2 "$api_url/api/health" 2>/dev/null \
    | grep -Eq '"service"[[:space:]]*:[[:space:]]*"arc3-runner"'
}

web_ready() {
  curl --silent --fail --max-time 2 "$web_url/" 2>/dev/null \
    | grep -Fq '<title>ARC3 Runner</title>'
}

port_owner() {
  lsof -nP -iTCP:"$1" -sTCP:LISTEN -t 2>/dev/null | head -n 1
}

if api_ready && web_ready; then
  open "$web_url"
  echo "ARC3 Runner 已在运行，已重新打开：$web_url"
  exit 0
fi

api_pid=""
web_pid=""

cleanup() {
  if [[ -n "$api_pid" ]]; then kill "$api_pid" 2>/dev/null || true; fi
  if [[ -n "$web_pid" ]]; then kill "$web_pid" 2>/dev/null || true; fi
}
trap cleanup EXIT INT TERM

if ! api_ready; then
  if api_pid="$(port_owner "$api_port")" && [[ -n "$api_pid" ]]; then
    echo "端口 $api_port 已被非 ARC3 Runner 服务占用（PID $api_pid）。" >&2
    exit 1
  fi
  (
    cd "$project_root"
    exec uv run uvicorn server.main:app --host 127.0.0.1 --port "$api_port"
  ) >"$runtime_dir/api.log" 2>&1 &
  api_pid=$!
  echo "$api_pid" >"$runtime_dir/api.pid"
fi

if ! web_ready; then
  if web_pid="$(port_owner "$web_port")" && [[ -n "$web_pid" ]]; then
    echo "端口 $web_port 已被非 ARC3 Runner 页面占用（PID $web_pid）。" >&2
    exit 1
  fi
  (
    cd "$project_root"
    exec npm --prefix web run dev -- --port "$web_port" --strictPort
  ) >"$runtime_dir/web.log" 2>&1 &
  web_pid=$!
  echo "$web_pid" >"$runtime_dir/web.pid"
fi

for _ in {1..120}; do
  if api_ready && web_ready; then
    open "$web_url"
    echo "ARC3 Runner 已打开：$web_url"
    wait_pids=()
    if [[ -n "$api_pid" ]]; then wait_pids+=("$api_pid"); fi
    if [[ -n "$web_pid" ]]; then wait_pids+=("$web_pid"); fi
    if ((${#wait_pids[@]})); then
      wait "${wait_pids[@]}"
    fi
    exit 0
  fi
  sleep 0.25
done

echo "ARC3 Runner 未在 30 秒内就绪。" >&2
echo "API 日志：$runtime_dir/api.log" >&2
echo "Web 日志：$runtime_dir/web.log" >&2
exit 1
