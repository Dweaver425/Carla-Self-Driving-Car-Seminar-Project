@echo off
setlocal enabledelayedexpansion

rem Quick iteration run:
rem - spawn 10 CARLA autopilot teacher cars at different locations
rem - run the current model in the background on every car
rem - record 5 simulated minutes of teacher data
rem - train one quick fine-tuned checkpoint from all 10 vehicle folders

set "HOST=127.0.0.1"
set "PORT=2000"
set "TM_PORT=8000"
set "VEHICLES=10"
set "STEPS=6000"
set "SPAWN_INDICES=1 8 15 22 29 36 43 50 57 64"
set "CURRENT_CHECKPOINT=models\carla_teacher_refined_cuda.pt"
set "DEVICE=cuda"
set "EPOCHS=2"
set "BATCH_SIZE=128"
set "NUM_WORKERS=8"
set "LEARNING_RATE=0.00005"
set "VAL_SPLIT=0.1"
set "LOG_INTERVAL=100"

for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "STAMP=%%I"
set "OUTPUT_ROOT=data\episodes\quick_10car_5min_!STAMP!"
set "NEXT_CHECKPOINT=models\carla_quick_10car_5min_!STAMP!_cuda.pt"

echo Quick 10-car model comparison and fine-tune
echo Current model: %CURRENT_CHECKPOINT%
echo Vehicles: %VEHICLES%
echo Steps: %STEPS%  ^(5 simulated minutes at 0.05 seconds per tick^)
echo Output root: %OUTPUT_ROOT%
echo New checkpoint: %NEXT_CHECKPOINT%
echo.
echo Start CARLA first. Optional traffic terminal from the CARLA installation folder:
echo py -3.12 PythonAPI\examples\generate_traffic.py --host %HOST% --port %PORT% --tm-port %TM_PORT% --number-of-vehicles 30 --number-of-walkers 60 --safe
echo.
echo Press any key here to begin.
pause >nul

py -3.12 main.py collect-fleet --backend carla --host %HOST% --port %PORT% --tm-port %TM_PORT% --vehicles %VEHICLES% --spawn-indices %SPAWN_INDICES% --steps %STEPS% --output-root "%OUTPUT_ROOT%" --checkpoint "%CURRENT_CHECKPOINT%" --target-speed 8 --lane-guard --traffic-rule-guard --quiet
if errorlevel 1 (
    echo Fleet comparison collection failed.
    exit /b 1
)

set "DATASETS="
for /l %%V in (1,1,%VEHICLES%) do (
    set "PAD=0%%V"
    set "VEHICLE_DIR=vehicle_!PAD:~-2!"
    set DATASETS=!DATASETS! "!OUTPUT_ROOT!\!VEHICLE_DIR!"
)

echo.
echo Training quick fine-tuned checkpoint...
py -3.12 main.py train --init-checkpoint "%CURRENT_CHECKPOINT%" --dataset %DATASETS% --output "%NEXT_CHECKPOINT%" --device %DEVICE% --epochs %EPOCHS% --batch-size %BATCH_SIZE% --num-workers %NUM_WORKERS% --learning-rate %LEARNING_RATE% --val-split %VAL_SPLIT% --log-interval %LOG_INTERVAL%
if errorlevel 1 (
    echo Quick fine-tune failed.
    exit /b 1
)

echo.
echo Quick iteration finished.
echo Compare summary: %OUTPUT_ROOT%\fleet_summary.json
echo New checkpoint: %NEXT_CHECKPOINT%
exit /b 0
