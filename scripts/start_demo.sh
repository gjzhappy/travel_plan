#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
AGENT_MODE=auto
if [[ ${1:-} == "--agent-mode" && -n ${2:-} ]]; then AGENT_MODE=$2; shift 2; fi
[[ $# -eq 0 && "$AGENT_MODE" =~ ^(auto|opencode|deterministic)$ ]] || { echo "Usage: $0 [--agent-mode auto|opencode|deterministic]" >&2; exit 2; }

command -v python >/dev/null 2>&1 || { echo "Error: Python 3.11+ is required." >&2; exit 1; }
PYTHON_VERSION=$(python -c 'import sys; assert sys.version_info >= (3,11), "Python 3.11+ is required"; print(".".join(map(str, sys.version_info[:3])))')
if command -v opencode >/dev/null 2>&1; then OPENCODE_STATUS=FOUND; AUTO_RUNTIME="OpenCode Agent"; else OPENCODE_STATUS="NOT FOUND"; AUTO_RUNTIME="Deterministic Offline Agent"; fi
if [[ $AGENT_MODE == opencode && $OPENCODE_STATUS == "NOT FOUND" ]]; then echo "Error: --agent-mode opencode requires the opencode command." >&2; exit 1; fi
[[ $AGENT_MODE == deterministic ]] && RUNTIME="Deterministic Offline Agent" || RUNTIME=$AUTO_RUNTIME

if [[ ! -f data/travel.db ]]; then echo "SQLite database not found; initializing from checked-in seed data..."; python scripts/init_db.py; fi
[[ -f data/demo/shanghai_family_trip.json ]] || { echo "Error: Demo scenario is missing." >&2; exit 1; }
PYTHONPATH=src python -c 'import travel_plan.web.server'

cat <<EOF
====================================
Shanghai AI Travel Planner Demo

Environment Check
Python: OK $PYTHON_VERSION

Knowledge Base:
SQLite offline
Qdrant offline
BGE embedding

External Providers:
Transport Mock
Weather Mock
Reservation Mock
Crowd Mock

Checking OpenCode...
OpenCode: $OPENCODE_STATUS
Agent Runtime: $RUNTIME
$( [[ $OPENCODE_STATUS == "NOT FOUND" ]] && printf '\nNote:\nDemo continues without OpenCode.\nWorkflow and Planner remain unchanged.' )

Starting Web Demo...
URL: http://localhost:8000
Demo: 上海亲子4日游
====================================
EOF
exec env PYTHONPATH=src python -m travel_plan.web.server --host 127.0.0.1 --port 8000 --agent-mode "$AGENT_MODE"
