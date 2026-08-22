#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

command -v python >/dev/null 2>&1 || { echo "Error: Python 3.11+ is required." >&2; exit 1; }
python -c 'import sys; assert sys.version_info >= (3, 11), "Python 3.11+ is required"'

if [[ ! -f data/travel.db ]]; then
  echo "SQLite database not found; initializing it from checked-in seed data..."
  python scripts/init_db.py
fi
[[ -f data/demo/shanghai_family_trip.json ]] || { echo "Error: Demo scenario is missing." >&2; exit 1; }
PYTHONPATH=src python -c 'import travel_plan.web.server'

echo ""
echo "Travel Planner Demo Started"
echo "URL: http://localhost:8000"
echo "Demo Scenario: 上海4天亲子游"
echo ""
exec env PYTHONPATH=src python -m travel_plan.web.server --host 127.0.0.1 --port 8000
