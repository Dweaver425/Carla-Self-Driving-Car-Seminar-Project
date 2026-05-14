@echo off
setlocal enabledelayedexpansion

rem Project-local compatibility shim for Command Prompt.
rem It lets commands like `py -3.12 main.py ...` use this project's venv
rem even when the Windows Python Launcher is not installed.

set "ORIGINAL_ARGS=%*"
set "PROJECT_PY=%~dp0.venv\Scripts\python.exe"

if "%~1"=="-3.12" shift
if "%~1"=="-3" shift

set "PY_ARGS="

:collect_args
if "%~1"=="" goto run_python
set "ARG=%~1"
set "PY_ARGS=!PY_ARGS! "!ARG!""
shift
goto collect_args

:run_python
if exist "%PROJECT_PY%" (
    "%PROJECT_PY%" -c "pass" >nul 2>nul
    if not errorlevel 1 (
        "%PROJECT_PY%" !PY_ARGS!
        exit /b !ERRORLEVEL!
    )
)

for /f "delims=" %%P in ('where py.exe 2^>nul') do (
    "%%P" %ORIGINAL_ARGS%
    exit /b !ERRORLEVEL!
)

echo Project Python is not available.
echo Reinstall Python 3.12 or recreate .venv, then retry this command.
exit /b 1
