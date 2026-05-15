@echo off
setlocal

rem Fast trainer for many TAR-indexed shard dataset roots.
rem The dataset file should contain one shard dataset root per line.

set "DATASET_FILE=%~1"
set "INIT_CHECKPOINT=%~2"
set "OUTPUT_CHECKPOINT=%~3"

if "%DEVICE%"=="" set "DEVICE=cuda"
if "%EPOCHS%"=="" set "EPOCHS=2"
if "%BATCH_SIZE%"=="" set "BATCH_SIZE=512"
if "%NUM_WORKERS%"=="" set "NUM_WORKERS=10"
if "%LEARNING_RATE%"=="" set "LEARNING_RATE=0.00005"
if "%VAL_SPLIT%"=="" set "VAL_SPLIT=0.1"
if "%LOG_INTERVAL%"=="" set "LOG_INTERVAL=50"

if "%DATASET_FILE%"=="" (
    echo Missing TAR shard dataset file.
    echo Usage: scripts\train_tar_shards_fast_windows.bat data\raw\...\datasets.txt models\start.pt models\next.pt
    exit /b 1
)
if "%INIT_CHECKPOINT%"=="" (
    echo Missing init checkpoint.
    exit /b 1
)
if "%OUTPUT_CHECKPOINT%"=="" (
    echo Missing output checkpoint.
    exit /b 1
)

echo Training TAR shard datasets:
echo Dataset file: %DATASET_FILE%
echo Init checkpoint: %INIT_CHECKPOINT%
echo Output checkpoint: %OUTPUT_CHECKPOINT%
echo Batch size: %BATCH_SIZE%
echo Num workers: %NUM_WORKERS%
echo.

py -3.12 main.py train --init-checkpoint "%INIT_CHECKPOINT%" --dataset-file "%DATASET_FILE%" --output "%OUTPUT_CHECKPOINT%" --device %DEVICE% --epochs %EPOCHS% --batch-size %BATCH_SIZE% --num-workers %NUM_WORKERS% --learning-rate %LEARNING_RATE% --val-split %VAL_SPLIT% --log-interval %LOG_INTERVAL%
exit /b %ERRORLEVEL%
