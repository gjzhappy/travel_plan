@echo off
setlocal
cd /d "%~dp0\.."

python --version >nul 2>&1 || (echo Error: Python 3.11+ is required. & exit /b 1)
python -c "import sys; assert sys.version_info >= (3,11), 'Python 3.11+ is required'" || exit /b 1
if not exist "data\travel.db" (
  echo SQLite database not found; initializing it from checked-in seed data...
  python scripts\init_db.py || exit /b 1
)
if not exist "data\demo\shanghai_family_trip.json" (echo Error: Demo scenario is missing. & exit /b 1)
set PYTHONPATH=src
python -c "import travel_plan.web.server" || exit /b 1

echo.
echo Travel Planner Demo Started
echo URL: http://localhost:8000
echo Demo Scenario: 上海4天亲子游
echo.
python -m travel_plan.web.server --host 127.0.0.1 --port 8000
