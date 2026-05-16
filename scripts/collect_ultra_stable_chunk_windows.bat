@echo off
if "%CODEX_DELAYED_EXPANSION_READY%"=="1" goto delayed_ready
set "CODEX_DELAYED_EXPANSION_READY=1"
cmd /v:on /c call "%~f0" %*
exit /b %ERRORLEVEL%

:delayed_ready
setlocal EnableExtensions EnableDelayedExpansion

rem Collects one tiny 3-car chunk and stops. Use this if full loops are unstable.
rem Optional first argument: starting checkpoint path.

set "HOST=127.0.0.1"
set "PORT=2000"
set "TM_PORT=8000"
set "VEHICLES=3"
set "SPAWN_INDICES=1 15 29"
set "STEPS=3000"
set "CURRENT_CHECKPOINT=%~1"
set "ARG_RUN_NAME=%~2"
if not "%ARG_RUN_NAME%"=="" set "RUN_NAME=%ARG_RUN_NAME%"

if "%CURRENT_CHECKPOINT%"=="" (
    for /f "delims=" %%C in ('powershell -NoProfile -Command "$patterns='10hr2cars*_cuda.pt','5hr2cars*_cuda.pt','shadow2cars*_cuda.pt','overnight2cars*_cuda.pt','quick10cars*_cuda.pt','quick2cars*_cuda.pt','stable1hr*_cuda.pt','ultra1hr*_cuda.pt','ultraOvernight*_cuda.pt','stopSigns*_cuda.pt','teacherRefined*_cuda.pt'; $m=Get-ChildItem -Path models -File | Where-Object { $n=$_.Name; ($patterns | Where-Object { $n -like $_ }) -and $n -notlike '*_epoch_*' } | Sort-Object LastWriteTime -Descending | Select-Object -First 1; if ($m) { $m.FullName }"') do set "CURRENT_CHECKPOINT=%%C"
)
if "%CURRENT_CHECKPOINT%"=="" set "CURRENT_CHECKPOINT=models\teacherRefined_v1_cuda.pt"

for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "STAMP=%%I"
if "%RUN_NAME%"=="" set "RUN_NAME=ultraChunk_!STAMP!"
set "OUTPUT_ROOT=data\episodes\%RUN_NAME%\chunk_1"
set "LOG_DIR=logs"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
set "COLLECT_LOG=%LOG_DIR%\%RUN_NAME%_chunk_1_collect.log"
if exist "data\episodes\%RUN_NAME%" (
    echo Run root already exists: data\episodes\%RUN_NAME%
    echo Use a new version name, for example ultraChunk_v2.
    exit /b 1
)

echo Ultra-stable single collection chunk
echo Checkpoint: %CURRENT_CHECKPOINT%
echo Vehicles: %VEHICLES%
echo Steps: %STEPS%
echo Output: %OUTPUT_ROOT%
echo.
echo Press any key to start.
pause >nul

py -3.12 main.py collect-fleet --backend carla --host %HOST% --port %PORT% --tm-port %TM_PORT% --vehicles %VEHICLES% --spawn-indices %SPAWN_INDICES% --steps %STEPS% --output-root "%OUTPUT_ROOT%" --checkpoint "%CURRENT_CHECKPOINT%" --target-speed 8 --lane-guard --traffic-rule-guard --quiet > "%COLLECT_LOG%" 2>&1
if errorlevel 1 (
    echo Collection failed.
    echo See log: %COLLECT_LOG%
    exit /b 1
)

echo.
echo Collection finished.
echo Summary: %OUTPUT_ROOT%\fleet_summary.json
echo Train with:
echo scripts\train_completed_chunk_windows.bat %OUTPUT_ROOT% "%CURRENT_CHECKPOINT%" models\%RUN_NAME%_cuda.pt
exit /b 0
