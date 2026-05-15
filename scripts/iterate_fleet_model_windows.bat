@echo off
setlocal enabledelayedexpansion

rem Iteratively improves the current model:
rem 1. collect 3 CARLA autopilot cars while the current model predicts in the background
rem 2. fine-tune from the current checkpoint using the newly collected vehicle folders
rem 3. use the new checkpoint for the next iteration

set "HOST=127.0.0.1"
set "PORT=2000"
set "TM_PORT=8000"
set "VEHICLES=3"
set "SPAWN_INDICES=1 8 15"
set "ITERATIONS=3"
set "STEPS_PER_ITERATION=120000"
set "CURRENT_CHECKPOINT=models\carla_teacher_refined_cuda.pt"
set "DEVICE=cuda"
set "EPOCHS=3"
set "BATCH_SIZE=128"
set "NUM_WORKERS=8"
set "LEARNING_RATE=0.00005"
set "VAL_SPLIT=0.1"
set "LOG_INTERVAL=100"

for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "STAMP=%%I"
set "RUN_ROOT=data\episodes\iterative_fleet_!STAMP!"

echo Iterative guided fleet improvement
echo Starting checkpoint: %CURRENT_CHECKPOINT%
echo Iterations: %ITERATIONS%
echo Vehicles per iteration: %VEHICLES%
echo Steps per iteration: %STEPS_PER_ITERATION%
echo Run root: %RUN_ROOT%
echo.
echo Start CARLA first. Optional traffic terminal from the CARLA installation folder:
echo py -3.12 PythonAPI\examples\generate_traffic.py --host %HOST% --port %PORT% --tm-port %TM_PORT% --number-of-vehicles 30 --number-of-walkers 60 --safe
echo.
echo Press any key here to begin.
pause >nul

for /l %%I in (1,1,%ITERATIONS%) do (
    set "ITER_OUT=!RUN_ROOT!\iteration_%%I"
    set "NEXT_CHECKPOINT=models\carla_iterative_fleet_%%I_cuda.pt"

    echo.
    echo [%%I/%ITERATIONS%] Collecting guided fleet data with !CURRENT_CHECKPOINT!
    py -3.12 main.py collect-fleet --backend carla --host %HOST% --port %PORT% --tm-port %TM_PORT% --vehicles %VEHICLES% --spawn-indices %SPAWN_INDICES% --steps %STEPS_PER_ITERATION% --output-root "!ITER_OUT!" --checkpoint "!CURRENT_CHECKPOINT!" --target-speed 8 --lane-guard --traffic-rule-guard --quiet
    if errorlevel 1 (
        echo Collection failed during iteration %%I.
        exit /b 1
    )

    echo.
    echo [%%I/%ITERATIONS%] Fine-tuning to !NEXT_CHECKPOINT!
    py -3.12 main.py train --init-checkpoint "!CURRENT_CHECKPOINT!" --dataset "!ITER_OUT!\vehicle_01" "!ITER_OUT!\vehicle_02" "!ITER_OUT!\vehicle_03" --output "!NEXT_CHECKPOINT!" --device %DEVICE% --epochs %EPOCHS% --batch-size %BATCH_SIZE% --num-workers %NUM_WORKERS% --learning-rate %LEARNING_RATE% --val-split %VAL_SPLIT% --log-interval %LOG_INTERVAL%
    if errorlevel 1 (
        echo Training failed during iteration %%I.
        exit /b 1
    )

    set "CURRENT_CHECKPOINT=!NEXT_CHECKPOINT!"
)

echo.
echo Iterative fleet training finished.
echo Final checkpoint: !CURRENT_CHECKPOINT!
exit /b 0
