@echo off
setlocal enabledelayedexpansion

rem Trains one combined model from all segment_* folders created by the
rem overnight collection script.

set "DATA_ROOT=data\episodes\carla_overnight_segments"
set "OUTPUT=models\carla_overnight_combined.pt"
set "DEVICE=cuda"
set "EPOCHS=10"
set "BATCH_SIZE=16"
set "NUM_WORKERS=6"
set "LOG_INTERVAL=100"

set "DATASETS="
for /d %%D in ("%DATA_ROOT%\segment_*") do (
    set "DATASETS=!DATASETS! "%%~fD""
)

if "%DATASETS%"=="" (
    echo No segment folders were found under %DATA_ROOT%.
    exit /b 1
)

.\.venv\Scripts\python.exe -u main.py train --dataset %DATASETS% --output "%OUTPUT%" --device %DEVICE% --epochs %EPOCHS% --batch-size %BATCH_SIZE% --num-workers %NUM_WORKERS% --log-interval %LOG_INTERVAL%
