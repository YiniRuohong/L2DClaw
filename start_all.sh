#!/usr/bin/env bash
set -euo pipefail

kill_port() {
  local port="$1"
  local name="$2"
  local pids

  pids=$(lsof -ti tcp:"$port" || true)
  if [[ -n "${pids}" ]]; then
    echo "Stopping ${name} on port ${port} (PID: ${pids})"
    kill ${pids} || true
    sleep 1
    pids=$(lsof -ti tcp:"$port" || true)
    if [[ -n "${pids}" ]]; then
      echo "Force killing ${name} on port ${port} (PID: ${pids})"
      kill -9 ${pids} || true
    fi
  else
    echo "No process found on port ${port} (${name})"
  fi
}

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
web_dir="${repo_root}/Open-LLM-VTuber-Web"

kill_port 12393 "backend"
kill_port 3000 "electron dev"

echo "Starting backend..."
( cd "${repo_root}" && uv run run_server.py ) &

sleep 2

echo "Starting Electron dev client..."
cd "${web_dir}"
exec npm run dev
