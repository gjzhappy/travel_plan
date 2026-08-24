@echo off
setlocal EnableExtensions

echo.
echo ========================================
echo  Shanghai AI Travel Planner Demo
echo ========================================
echo.
echo [START] Launching demo...

set "SCRIPT_DIR=%~dp0"
where py >nul 2>&1
if not errorlevel 1 goto use_py
where python >nul 2>&1
if not errorlevel 1 goto use_python

echo [ERROR] Python 3.11+ was not found.
echo Please install Python and try again.
pause
exit /b 1

:use_py
py -3 "%SCRIPT_DIR%start_demo.py" %*
set "EXIT_CODE=%ERRORLEVEL%"
goto finish

:use_python
python "%SCRIPT_DIR%start_demo.py" %*
set "EXIT_CODE=%ERRORLEVEL%"
goto finish

:finish
if not "%EXIT_CODE%"=="0" pause
exit /b %EXIT_CODE%
