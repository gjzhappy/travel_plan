@echo off
setlocal EnableExtensions

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

rem Binding a temporary socket provides a deterministic port availability check.
python -c "import socket; s=socket.socket(); s.bind(('127.0.0.1',8000)); s.close()" >>"%LOG%" 2>&1 || goto :port_busy

if not exist "%ROOT%\data\travel.db" (
  echo [INFO] SQLite database not found; initializing from seed data...
  echo [INFO] Initializing SQLite database>>"%LOG%"
  python "%ROOT%\scripts\init_db.py" >>"%LOG%" 2>&1 || goto :database_error
)

echo.
echo Travel Planner Demo Started
echo URL: http://localhost:8000
echo Demo: Shanghai Family Trip
echo.
echo [INFO] Starting Web Server>>"%LOG%"
echo [INFO] Command: python -m travel_plan.web.server --host 127.0.0.1 --port 8000>>"%LOG%"
python -m travel_plan.web.server --host 127.0.0.1 --port 8000 >>"%LOG%" 2>&1
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
