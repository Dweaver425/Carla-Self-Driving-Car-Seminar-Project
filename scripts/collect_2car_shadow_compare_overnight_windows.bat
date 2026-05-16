@echo off
if not "%CODEX_DELAYED_EXPANSION_READY%"=="1" (
    set "CODEX_DELAYED_EXPANSION_READY=1"
    cmd /v:on /c call "%~f0" %*
    exit /b %ERRORLEVEL%
)
setlocal EnableExtensions EnableDelayedExpansion

rem Overnight CARLA-teacher shadow comparison.
rem CARLA autopilot drives. The checkpoint predicts raw requested_control in
rem shadow mode so we can compare model behavior against the CARLA teacher.

if "%HOST%"=="" set "HOST=127.0.0.1"
if "%PORT%"=="" set "PORT=2000"
if "%TM_PORT%"=="" set "TM_PORT=8000"
if "%VEHICLES%"=="" set "VEHICLES=2"
if "%SPAWN_INDICES%"=="" set "SPAWN_INDICES=33 31"
if "%STEPS%"=="" set "STEPS=2500"
if "%DURATION_HOURS%"=="" set "DURATION_HOURS=10"
if "%RUN_LABEL%"=="" set "RUN_LABEL=shadow_compare_2car"
if "%LOG_LABEL%"=="" set "LOG_LABEL=shadow_compare_2car"
set "CURRENT_CHECKPOINT=%~1"

if "%CURRENT_CHECKPOINT%"=="" (
    echo Missing model checkpoint.
    echo Usage: scripts\collect_2car_shadow_compare_overnight_windows.bat models\your_model.pt
    exit /b 1
)

for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "STAMP=%%I"
for /f %%I in ('powershell -NoProfile -Command "[DateTimeOffset]::Now.AddHours(%DURATION_HOURS%).ToUnixTimeSeconds()"') do set "END_EPOCH=%%I"
for /f "delims=" %%I in ('powershell -NoProfile -Command "(Get-Date).AddHours(%DURATION_HOURS%).ToString('yyyy-MM-dd HH:mm:ss')"') do set "END_LOCAL=%%I"

set "RUN_ROOT=data\episodes\%RUN_LABEL%_%STAMP%"
set "LOG_DIR=logs"
set "CONTROL_SUMMARY=%LOG_DIR%\%LOG_LABEL%_%STAMP%_control_summary.json"
set "STOP_SUMMARY=%LOG_DIR%\%LOG_LABEL%_%STAMP%_stop_sign_summary.json"
set "STOP_EVENTS=%LOG_DIR%\%LOG_LABEL%_%STAMP%_stop_sign_events.csv"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

echo Overnight shadow comparison
echo Checkpoint: %CURRENT_CHECKPOINT%
echo Duration hours: %DURATION_HOURS%
echo Ends around: %END_LOCAL%
echo Vehicles: %VEHICLES%
echo Spawn indices: %SPAWN_INDICES%
echo Steps per chunk: %STEPS%
echo Run root: %RUN_ROOT%
echo.
echo CARLA autopilot drives. The model is recorded raw in shadow mode.
echo Press any key to start.
pause >nul

for /l %%I in (1,1,9999) do (
    for /f %%T in ('powershell -NoProfile -Command "[DateTimeOffset]::Now.ToUnixTimeSeconds()"') do set "NOW_EPOCH=%%T"
    if !NOW_EPOCH! GEQ %END_EPOCH% goto finished

    echo.
    echo [chunk %%I] Collecting %RUN_ROOT%\chunk_%%I
    call py -3.12 main.py collect-fleet --backend carla --host %HOST% --port %PORT% --tm-port %TM_PORT% --vehicles %VEHICLES% --spawn-indices %SPAWN_INDICES% --steps %STEPS% --output-root "%RUN_ROOT%\chunk_%%I" --checkpoint "%CURRENT_CHECKPOINT%" --target-speed 8 --quiet > "%LOG_DIR%\%LOG_LABEL%_%STAMP%_chunk_%%I_collect.log" 2>&1
    if errorlevel 1 (
        echo Collection failed during chunk %%I.
        echo See log: %LOG_DIR%\%LOG_LABEL%_%STAMP%_chunk_%%I_collect.log
        echo Completed chunks before this one can still be analyzed or trained.
        exit /b 1
    )
)

:finished
echo.
echo Collection finished or timer expired.
echo Run root: %RUN_ROOT%
echo.
echo Analyzing model-vs-CARLA control differences...
call py -3.12 scripts\analyze_shadow_control_deltas.py --dataset-root "%RUN_ROOT%" --output-json "%CONTROL_SUMMARY%"
if errorlevel 1 (
    echo Control-delta analysis failed.
    echo You can retry with:
    echo py -3.12 scripts\analyze_shadow_control_deltas.py --dataset-root "%RUN_ROOT%" --output-json "%CONTROL_SUMMARY%"
    exit /b 1
)

echo.
echo Analyzing stop-sign response...
call py -3.12 scripts\analyze_stop_sign_response.py --dataset-root "%RUN_ROOT%" --output-csv "%STOP_EVENTS%" > "%STOP_SUMMARY%"
if errorlevel 1 (
    echo Stop-sign analysis failed.
    echo You can retry with:
    echo py -3.12 scripts\analyze_stop_sign_response.py --dataset-root "%RUN_ROOT%" --output-csv "%STOP_EVENTS%"
    exit /b 1
)

type "%STOP_SUMMARY%"
echo.
echo Control summary: %CONTROL_SUMMARY%
echo Stop-sign summary: %STOP_SUMMARY%
echo Stop-sign events: %STOP_EVENTS%
echo Train later from completed chunks with a mixed dataset-file if the comparison looks useful.
exit /b 0
