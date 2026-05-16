@echo off
setlocal

rem Collect a short CARLA-teacher run and compare stop-sign frames against the
rem raw shadow model response. CARLA autopilot drives safely; the checkpoint
rem only predicts requested_control for analysis. Traffic-rule guard is
rem intentionally off here so it does not hide the model's own stop-sign behavior.

if "%HOST%"=="" set "HOST=127.0.0.1"
if "%PORT%"=="" set "PORT=2000"
if "%TM_PORT%"=="" set "TM_PORT=8000"
if "%VEHICLES%"=="" set "VEHICLES=2"
if "%SPAWN_INDICES%"=="" set "SPAWN_INDICES=1 29"
if "%STEPS%"=="" set "STEPS=10000"
set "CURRENT_CHECKPOINT=%~1"
set "ARG_RUN_NAME=%~2"
if not "%ARG_RUN_NAME%"=="" set "RUN_NAME=%ARG_RUN_NAME%"

if "%CURRENT_CHECKPOINT%"=="" (
    echo Missing model checkpoint.
    echo Usage: scripts\collect_stop_sign_compare_windows.bat models\your_model.pt [run_name]
    exit /b 1
)

for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "STAMP=%%I"
if "%RUN_NAME%"=="" set "RUN_NAME=stopSigns_%STAMP%"
set "RUN_ROOT=data\episodes\%RUN_NAME%"
set "LOG_DIR=logs"
set "COLLECT_LOG=%LOG_DIR%\%RUN_NAME%_collect.log"
set "SUMMARY_JSON=%LOG_DIR%\%RUN_NAME%_summary.json"
set "EVENTS_CSV=%LOG_DIR%\%RUN_NAME%_events.csv"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
if exist "%RUN_ROOT%" (
    echo Run root already exists: %RUN_ROOT%
    echo Use a new version name, for example stopSigns_v2.
    exit /b 1
)

echo Stop-sign comparison collection
echo Checkpoint: %CURRENT_CHECKPOINT%
echo Run name: %RUN_NAME%
echo Output: %RUN_ROOT%
echo Vehicles: %VEHICLES%
echo Steps: %STEPS%
echo.

call py -3.12 main.py collect-fleet --backend carla --host %HOST% --port %PORT% --tm-port %TM_PORT% --vehicles %VEHICLES% --spawn-indices %SPAWN_INDICES% --steps %STEPS% --output-root "%RUN_ROOT%" --checkpoint "%CURRENT_CHECKPOINT%" --target-speed 8 --quiet > "%COLLECT_LOG%" 2>&1
if errorlevel 1 (
    echo Collection failed.
    echo See log: %COLLECT_LOG%
    exit /b 1
)

call py -3.12 scripts\analyze_stop_sign_response.py --dataset-root "%RUN_ROOT%" --output-csv "%EVENTS_CSV%" > "%SUMMARY_JSON%"
if errorlevel 1 (
    echo Stop-sign analysis failed.
    echo Collection log: %COLLECT_LOG%
    exit /b 1
)

type "%SUMMARY_JSON%"
echo.
echo Collection log: %COLLECT_LOG%
echo Event CSV: %EVENTS_CSV%
exit /b 0
