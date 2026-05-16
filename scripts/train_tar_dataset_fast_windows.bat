@echo off
setlocal

rem Fast trainer for one TAR-indexed dataset root.
rem The dataset root must contain manifest.jsonl, metadata.json,
rem tar_image_index.jsonl, and tar_image_index_metadata.json.

set "DATASET_ROOT=%~1"
set "INIT_CHECKPOINT=%~2"
set "OUTPUT_CHECKPOINT=%~3"

if "%DEVICE%"=="" set "DEVICE=cuda"
if "%EPOCHS%"=="" set "EPOCHS=2"
if "%BATCH_SIZE%"=="" set "BATCH_SIZE=512"
rem Windows can fail with RuntimeError 1455 when too many workers create
rem shared tensor mappings at a high batch size. Four keeps TAR training fast
rem while avoiding the paging-file/shared-memory failure seen with 10 workers.
if "%NUM_WORKERS%"=="" set "NUM_WORKERS=4"
if "%LEARNING_RATE%"=="" set "LEARNING_RATE=0.00005"
if "%VAL_SPLIT%"=="" set "VAL_SPLIT=0.1"
if "%LOG_INTERVAL%"=="" set "LOG_INTERVAL=50"

if "%DATASET_ROOT%"=="" (
    echo Missing TAR-indexed dataset root.
    echo Usage: scripts\train_tar_dataset_fast_windows.bat data\raw\...\dataset_name models\start.pt models\next.pt
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

echo Training TAR-indexed dataset:
echo Dataset root: %DATASET_ROOT%
echo Init checkpoint: %INIT_CHECKPOINT%
echo Output checkpoint: %OUTPUT_CHECKPOINT%
echo Batch size: %BATCH_SIZE%
echo Num workers: %NUM_WORKERS%
echo.

py -3.12 main.py train --init-checkpoint "%INIT_CHECKPOINT%" --dataset "%DATASET_ROOT%" --output "%OUTPUT_CHECKPOINT%" --device %DEVICE% --epochs %EPOCHS% --batch-size %BATCH_SIZE% --num-workers %NUM_WORKERS% --learning-rate %LEARNING_RATE% --val-split %VAL_SPLIT% --log-interval %LOG_INTERVAL%
exit /b %ERRORLEVEL%
