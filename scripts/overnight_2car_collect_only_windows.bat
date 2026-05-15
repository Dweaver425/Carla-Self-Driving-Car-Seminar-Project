@echo off
setlocal EnableExtensions EnableDelayedExpansion

rem Most reliable overnight mode:
rem - only 2 CARLA autopilot teacher cars
rem - short 2500-step chunks
rem - collection only, no training inside the overnight loop
rem Train the completed chunks in the morning.

set "HOST=127.0.0.1"
set "PORT=2000"
set "TM_PORT=8000"
set "VEHICLES=2"
set "SPAWN_INDICES=1 29"
set "STEPS=2500"
set "CHUNKS=96"
set "CURRENT_CHECKPOINT=%~1"

if "%CURRENT_CHECKPOINT%"=="" (
    for /f "delims=" %%C in ('powershell -NoProfile -Command "$m=Get-ChildItem -Path models -File | Where-Object { ($_.Name -like 'carla_quick*_cuda.pt' -or $_.Name -like 'stable_*_cuda.pt' -or $_.Name -like 'ultra_*_cuda.pt') -and $_.Name -notlike '*_epoch_*' } | Sort-Object LastWriteTime -Descending | Select-Object -First 1; if ($m) { $m.FullName }"') do set "CURRENT_CHECKPOINT=%%C"
)
if "%CURRENT_CHECKPOINT%"=="" set "CURRENT_CHECKPOINT=models\carla_teacher_refined_cuda.pt"

for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "STAMP=%%I"
set "RUN_ROOT=data\episodes\overnight_2car_collect_!STAMP!"
set "LOG_DIR=logs"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

echo 2-car collect-only overnight mode
echo Checkpoint: %CURRENT_CHECKPOINT%
echo Chunks: %CHUNKS%
echo Vehicles: %VEHICLES%
echo Steps per chunk: %STEPS%
echo Run root: %RUN_ROOT%
echo.
echo This does not train during the overnight loop. Train completed chunks later.
echo Press any key to start.
pause >nul

for /l %%I in (1,1,%CHUNKS%) do (
    set "CHUNK_OUT=!RUN_ROOT!\chunk_%%I"
    set "COLLECT_LOG=%LOG_DIR%\overnight_2car_!STAMP!_chunk_%%I_collect.log"

    echo.
    echo [%%I/%CHUNKS%] Collecting !CHUNK_OUT!
    py -3.12 main.py collect-fleet --backend carla --host %HOST% --port %PORT% --tm-port %TM_PORT% --vehicles %VEHICLES% --spawn-indices %SPAWN_INDICES% --steps %STEPS% --output-root "!CHUNK_OUT!" --checkpoint "%CURRENT_CHECKPOINT%" --target-speed 8 --lane-guard --traffic-rule-guard --quiet > "!COLLECT_LOG!" 2>&1
    if errorlevel 1 (
        echo Collection failed during chunk %%I.
        echo See log: !COLLECT_LOG!
        exit /b 1
    )
)

echo.
echo 2-car overnight collection finished.
echo Run root: %RUN_ROOT%
echo Train later with scripts\train_collected_chunks_windows.bat
exit /b 0
