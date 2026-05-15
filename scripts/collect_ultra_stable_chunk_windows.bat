@echo off
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

if "%CURRENT_CHECKPOINT%"=="" (
    for /f "delims=" %%C in ('powershell -NoProfile -Command "$m=Get-ChildItem -Path models -File | Where-Object { ($_.Name -like 'carla_quick*_cuda.pt' -or $_.Name -like 'stable_*_cuda.pt' -or $_.Name -like 'ultra_*_cuda.pt') -and $_.Name -notlike '*_epoch_*' } | Sort-Object LastWriteTime -Descending | Select-Object -First 1; if ($m) { $m.FullName }"') do set "CURRENT_CHECKPOINT=%%C"
)
if "%CURRENT_CHECKPOINT%"=="" set "CURRENT_CHECKPOINT=models\carla_teacher_refined_cuda.pt"

for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "STAMP=%%I"
set "OUTPUT_ROOT=data\episodes\ultra_chunk_!STAMP!\iteration_1"
set "LOG_DIR=logs"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
set "COLLECT_LOG=%LOG_DIR%\ultra_chunk_!STAMP!_collect.log"

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
echo scripts\train_completed_iteration_windows.bat %OUTPUT_ROOT% "%CURRENT_CHECKPOINT%" models\ultra_chunk_!STAMP!_cuda.pt
exit /b 0
