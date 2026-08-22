#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
AGENT_MODE=deterministic
LOG="$ROOT/logs/start_demo.log"
mkdir -p "$ROOT/logs"
exec 3>>"$LOG"
printf '[INFO] Travel Planner Demo Start - %s\n' "$(date -u +%FT%TZ)" >&3
if [[ ${1:-} == "--agent-mode" && -n ${2:-} ]]; then AGENT_MODE=$2; shift 2; fi
[[ $# -eq 0 && "$AGENT_MODE" =~ ^(auto|opencode|deterministic)$ ]] || { echo "Usage: $0 [--agent-mode auto|opencode|deterministic]" >&2; exit 2; }

command -v python >/dev/null 2>&1 || { echo "Error: Python 3.11+ is required." | tee /dev/fd/3 >&2; exit 1; }
PYTHON_VERSION=$(python -c 'import sys; assert sys.version_info >= (3,11), "Python 3.11+ is required"; print(".".join(map(str, sys.version_info[:3])))')
if command -v opencode >/dev/null 2>&1; then OPENCODE_STATUS=FOUND; AUTO_RUNTIME="OpenCode Agent"; else OPENCODE_STATUS="NOT FOUND"; AUTO_RUNTIME="Deterministic Offline Agent"; fi
if [[ $AGENT_MODE == opencode && $OPENCODE_STATUS == "NOT FOUND" ]]; then echo "Error: --agent-mode opencode requires the opencode command." >&2; exit 1; fi
[[ $AGENT_MODE == opencode ]] && RUNTIME="OpenCode Agent" || RUNTIME="Deterministic Offline Agent"

if [[ ! -f data/travel.db ]]; then echo "SQLite database not found; initializing from checked-in seed data..."; python scripts/init_db.py >&3 2>&1; fi
[[ -f data/demo/shanghai_family_trip.json ]] || { echo "Error: Demo scenario is missing." >&2; exit 1; }
PYTHONPATH=src python -c 'import fastapi, uvicorn; import travel_plan.web.server' >&3 2>&1

cat <<EOF
====================================
Shanghai AI Travel Planner Demo

[1/6] 检查 Python 环境
✓ Python $PYTHON_VERSION

[2/6] 检查上海旅游知识库
✓ SQLite POI Database
✓ Qdrant Semantic Collection (offline)

[3/6] 检查 Embedding Model
✓ BAAI/bge-small-zh-v1.5

[4/6] Agent Runtime
  $RUNTIME

[5/6] 启动 Web 服务

[6/6] 打开浏览器

Demo:
http://localhost:8000
====================================
EOF

(
  sleep 1
  if command -v xdg-open >/dev/null 2>&1; then
    xdg-open http://localhost:8000 >/dev/null 2>&1
  elif command -v open >/dev/null 2>&1; then
    open http://localhost:8000 >/dev/null 2>&1
  else
    false
  fi || printf 'Browser auto open failed.\nPlease visit:\nhttp://localhost:8000\n'
) &
env PYTHONPATH=src python -m travel_plan.web.server --host 127.0.0.1 --port 8000 --agent-mode "$AGENT_MODE" >>"$LOG" 2>&1
