@echo off
setlocal EnableExtensions
set "AGENT_MODE=auto"
if /i "%~1"=="--agent-mode" (
  set "AGENT_MODE=%~2"
  if "%~2"=="" goto :usage
  shift
  shift
)
if not "%~1"=="" goto :usage

rem Resolve the repository from this script, not from the caller's directory.
for %%I in ("%~dp0..") do set "ROOT=%%~fI"
cd /d "%ROOT%" || goto :root_error

if not exist "logs" mkdir "logs" >nul 2>&1
set "LOG=%ROOT%\logs\start_demo.log"
>"%LOG%" echo [INFO] Travel Planner Demo Start - %date% %time%
>>"%LOG%" echo [INFO] Root: %ROOT%
>>"%LOG%" echo [INFO] Working directory: %CD%

where python >nul 2>&1 || goto :python_missing
python --version >>"%LOG%" 2>&1 || goto :python_missing
python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >>"%LOG%" 2>&1 || goto :python_version
for /f "tokens=*" %%V in ('python --version 2^>^&1') do set "PYTHON_VERSION=%%V"
echo [INFO] Python: %PYTHON_VERSION%>>"%LOG%"

set "PYTHONPATH=%ROOT%\src;%PYTHONPATH%"
echo [INFO] PYTHONPATH: %PYTHONPATH%>>"%LOG%"

if not exist "%ROOT%\src\travel_plan\web\server.py" goto :server_missing
if not exist "%ROOT%\data\demo\shanghai_family_trip.json" goto :scenario_missing

rem Validate the packaged demo dependencies without changing the environment.
python -c "import fastapi, uvicorn" >>"%LOG%" 2>&1 || goto :dependencies_missing
python -c "import travel_plan.web.server" >>"%LOG%" 2>&1 || goto :module_error

where opencode >nul 2>&1
if errorlevel 1 (
  set "OPENCODE_STATUS=NOT FOUND"
  set "AUTO_RUNTIME=Deterministic Offline Agent"
) else (
  set "OPENCODE_STATUS=FOUND"
  set "AUTO_RUNTIME=OpenCode Agent"
)
if /i "%AGENT_MODE%"=="opencode" if "%OPENCODE_STATUS%"=="NOT FOUND" goto :opencode_missing
if /i "%AGENT_MODE%"=="deterministic" (set "AGENT_RUNTIME=Deterministic Offline Agent") else (set "AGENT_RUNTIME=%AUTO_RUNTIME%")

rem Binding a temporary socket provides a deterministic port availability check.
python -c "import socket; s=socket.socket(); s.bind(('127.0.0.1',8000)); s.close()" >>"%LOG%" 2>&1 || goto :port_busy

if not exist "%ROOT%\data\travel.db" (
  echo [INFO] SQLite database not found; initializing from seed data...
  echo [INFO] Initializing SQLite database>>"%LOG%"
  python "%ROOT%\scripts\init_db.py" >>"%LOG%" 2>&1 || goto :database_error
)

echo.
echo ====================================
echo Shanghai AI Travel Planner Demo
echo Environment Check
echo Python: OK %PYTHON_VERSION%
echo Knowledge Base: SQLite offline, Qdrant offline, BGE embedding
echo External Providers: Transport Mock, Weather Mock, Reservation Mock, Crowd Mock
echo Checking OpenCode...
echo OpenCode: %OPENCODE_STATUS%
echo Agent Runtime: %AGENT_RUNTIME%
if "%OPENCODE_STATUS%"=="NOT FOUND" echo Note: Demo continues without OpenCode. Workflow and Planner remain unchanged.
echo Starting Web Demo...
echo URL: http://localhost:8000
echo Demo: Shanghai Family Trip
echo ====================================
echo.
echo [INFO] Starting Web Server>>"%LOG%"
echo [INFO] Command: python -m travel_plan.web.server --host 127.0.0.1 --port 8000>>"%LOG%"
python -m travel_plan.web.server --host 127.0.0.1 --port 8000 --agent-mode "%AGENT_MODE%" >>"%LOG%" 2>&1
if errorlevel 1 goto :server_error
goto :success

:root_error
echo.
echo [ERROR]
echo Project root could not be opened: %~dp0..
goto :failed_without_log

:python_missing
call :error "Python not found" "Please install Python 3.11+."
goto :failed

:python_version
call :error "Unsupported Python version" "Please install Python 3.11 or newer."
goto :failed

:server_missing
call :error "Critical file is missing" "src\travel_plan\web\server.py"
goto :failed

:scenario_missing
call :error "Demo scenario is missing" "data\demo\shanghai_family_trip.json"
goto :failed

:dependencies_missing
call :error "Required Python modules are unavailable: fastapi and/or uvicorn" "Please run: pip install -r requirements.txt"
goto :failed

:opencode_missing
call :error "OpenCode not found" "--agent-mode opencode requires the opencode command."
goto :failed

:usage
echo Usage: start_demo.bat [--agent-mode auto^|opencode^|deterministic]
goto :failed_without_log

:module_error
call :error "Module import failed" "See the traceback in the log."
goto :failed

:port_busy
call :error "Port 8000 is already in use" "Please stop the existing server or use another port."
goto :failed

:database_error
call :error "Demo database initialization failed" "See the traceback in the log."
goto :failed

:server_error
call :error "Web server exited with an error" "See the traceback in the log."
goto :failed

:error
echo [ERROR] %~1>>"%LOG%"
echo.
echo [ERROR]
echo %~1
echo %~2
echo.
echo Log saved: %LOG%
exit /b 0

:failed
echo Press any key to exit.
pause >nul
exit /b 1

:failed_without_log
echo Press any key to exit.
pause >nul
exit /b 1

:success
echo [INFO] Web server stopped normally.>>"%LOG%"
echo.
echo Web server stopped.
echo Log saved: %LOG%
echo Press any key to exit.
pause >nul
exit /b 0
