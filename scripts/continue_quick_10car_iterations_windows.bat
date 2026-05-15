@echo off
setlocal EnableExtensions EnableDelayedExpansion

rem Repeats the quick 10-car / 5-sim-minute loop several times.
rem Each round uses the checkpoint produced by the previous round.

set "HOST=127.0.0.1"
set "PORT=2000"
set "TM_PORT=8000"
set "VEHICLES=10"
set "STEPS=6000"
set "SPAWN_INDICES=1 8 15 22 29 36 43 50 57 64"
set "ITERATIONS=3"
set "CURRENT_CHECKPOINT=%~1"
set "DEVICE=cuda"
set "EPOCHS=2"
set "BATCH_SIZE=128"
set "NUM_WORKERS=0"
set "LEARNING_RATE=0.00005"
set "VAL_SPLIT=0.1"
set "LOG_INTERVAL=100"

if "%CURRENT_CHECKPOINT%"=="" (
    for /f "delims=" %%C in ('powershell -NoProfile -Command "$m=Get-ChildItem -Path models -File | Where-Object { ($_.Name -like 'carla_quick*_cuda.pt' -or $_.Name -like 'stable_*_cuda.pt' -or $_.Name -like 'ultra_*_cuda.pt') -and $_.Name -notlike '*_epoch_*' } | Sort-Object LastWriteTime -Descending | Select-Object -First 1; if ($m) { $m.FullName }"') do set "CURRENT_CHECKPOINT=%%C"
)
if "%CURRENT_CHECKPOINT%"=="" set "CURRENT_CHECKPOINT=models\carla_teacher_refined_cuda.pt"

for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "STAMP=%%I"
set "RUN_ROOT=data\episodes\quick_10car_continue_!STAMP!"
set "LOG_DIR=logs"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

echo Continuing quick 10-car iterations
echo Starting checkpoint: %CURRENT_CHECKPOINT%
echo Iterations: %ITERATIONS%
echo Vehicles: %VEHICLES%
echo Steps per iteration: %STEPS%
echo Run root: %RUN_ROOT%
echo.
echo Start CARLA first. Optional traffic terminal from the CARLA installation folder:
echo py -3.12 PythonAPI\examples\generate_traffic.py --host %HOST% --port %PORT% --tm-port %TM_PORT% --number-of-vehicles 30 --number-of-walkers 60 --safe
echo.
echo Press any key here to begin.
pause >nul

for /l %%I in (1,1,%ITERATIONS%) do (
    set "ITER_OUT=!RUN_ROOT!\iteration_%%I"
    set "NEXT_CHECKPOINT=models\carla_quick_continue_!STAMP!_iter_%%I_cuda.pt"
    set "COLLECT_LOG=%LOG_DIR%\quick_continue_!STAMP!_iter_%%I_collect.log"
    set "TRAIN_LOG=%LOG_DIR%\quick_continue_!STAMP!_iter_%%I_train.log"

    echo.
    echo [%%I/%ITERATIONS%] Collecting 10-car comparison with !CURRENT_CHECKPOINT!
    py -3.12 main.py collect-fleet --backend carla --host %HOST% --port %PORT% --tm-port %TM_PORT% --vehicles %VEHICLES% --spawn-indices %SPAWN_INDICES% --steps %STEPS% --output-root "!ITER_OUT!" --checkpoint "!CURRENT_CHECKPOINT!" --target-speed 8 --lane-guard --traffic-rule-guard --quiet > "!COLLECT_LOG!" 2>&1
    if errorlevel 1 (
        echo Collection failed during iteration %%I.
        echo See log: !COLLECT_LOG!
        exit /b 1
    )

    set "DATASETS="
    for /l %%V in (1,1,%VEHICLES%) do (
        set "PAD=0%%V"
        set "VEHICLE_DIR=vehicle_!PAD:~-2!"
        set DATASETS=!DATASETS! "!ITER_OUT!\!VEHICLE_DIR!"
    )

    echo.
    echo [%%I/%ITERATIONS%] Fine-tuning to !NEXT_CHECKPOINT!
    py -3.12 main.py train --init-checkpoint "!CURRENT_CHECKPOINT!" --dataset !DATASETS! --output "!NEXT_CHECKPOINT!" --device %DEVICE% --epochs %EPOCHS% --batch-size %BATCH_SIZE% --num-workers %NUM_WORKERS% --learning-rate %LEARNING_RATE% --val-split %VAL_SPLIT% --log-interval %LOG_INTERVAL% > "!TRAIN_LOG!" 2>&1
    if errorlevel 1 (
        echo Training failed during iteration %%I.
        echo See log: !TRAIN_LOG!
        exit /b 1
    )

    set "CURRENT_CHECKPOINT=!NEXT_CHECKPOINT!"
)

echo.
echo Quick continuation finished.
echo Final checkpoint: !CURRENT_CHECKPOINT!
exit /b 0
