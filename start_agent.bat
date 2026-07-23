@echo off
setlocal EnableExtensions
cd /d "%~dp0"

title Shiyishang Agent Chat

set "PYTHON_EXE="
if exist ".venv\Scripts\python.exe" set "PYTHON_EXE=%CD%\.venv\Scripts\python.exe"

if not defined PYTHON_EXE (
    where python.exe >nul 2>&1
    if not errorlevel 1 set "PYTHON_EXE=python.exe"
)

if not defined PYTHON_EXE (
    where py.exe >nul 2>&1
    if not errorlevel 1 set "PYTHON_EXE=py.exe"
)

if not defined PYTHON_EXE (
    echo [ERROR] Python 3.10 or newer was not found.
    echo Install Python and enable "Add Python to PATH", then run this file again.
    pause
    exit /b 1
)

"%PYTHON_EXE%" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python 3.10 or newer is required.
    "%PYTHON_EXE%" --version
    pause
    exit /b 1
)

"%PYTHON_EXE%" -c "import shiyishang_agent" >nul 2>&1
if errorlevel 1 (
    echo [SETUP] Installing the local agent package...
    "%PYTHON_EXE%" -m pip install -e .
    if errorlevel 1 (
        echo [ERROR] Package installation failed.
        pause
        exit /b 1
    )
)

if not exist "KEYS\APIKEY.env" (
    echo [ERROR] KEYS\APIKEY.env was not found.
    pause
    exit /b 1
)

echo ============================================================
echo  Shiyishang Agent - type /exit to end the chat
echo ============================================================
echo.

"%PYTHON_EXE%" -m shiyishang_agent --session manual-chat %*
set "AGENT_EXIT=%ERRORLEVEL%"

echo.
if not "%AGENT_EXIT%"=="0" echo [ERROR] Agent exited with code %AGENT_EXIT%.
echo Chat ended. Press any key to close this window.
pause >nul
exit /b %AGENT_EXIT%
