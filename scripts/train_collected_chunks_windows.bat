@echo off
if not "%CODEX_DELAYED_EXPANSION_READY%"=="1" (
    set "CODEX_DELAYED_EXPANSION_READY=1"
    cmd /v:on /c call "%~f0" %*
    exit /b %ERRORLEVEL%
)
setlocal EnableExtensions EnableDelayedExpansion

rem Trains one checkpoint from all completed chunk_*/vehicle_* folders under a run root.
rem Usage:
rem   scripts\train_collected_chunks_windows.bat data\episodes\overnight_2car_collect_YYYYMMDD_HHMMSS models\start.pt models\next.pt

set "RUN_ROOT=%~1"
set "INIT_CHECKPOINT=%~2"
set "OUTPUT_CHECKPOINT=%~3"
set "DEVICE=cuda"
set "EPOCHS=2"
set "BATCH_SIZE=64"
if "%NUM_WORKERS%"=="" set "NUM_WORKERS=4"
set "LEARNING_RATE=0.00005"
set "VAL_SPLIT=0.1"
set "LOG_INTERVAL=100"
set "LOG_DIR=logs"
set "DATASET_FILE=%LOG_DIR%\%~n3_datasets.txt"

if "%RUN_ROOT%"=="" (
    echo Missing run root.
    echo Usage: scripts\train_collected_chunks_windows.bat data\episodes\overnight_2car_collect_YYYYMMDD_HHMMSS models\start.pt models\next.pt
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
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
type nul > "%DATASET_FILE%"

set "DATASET_COUNT=0"
for /d %%C in ("%RUN_ROOT%\chunk_*") do (
    if exist "%%~fC\fleet_summary.json" (
        for /d %%V in ("%%~fC\vehicle_*") do (
            if exist "%%~fV\metadata.json" (
                set /a DATASET_COUNT+=1
                >> "%DATASET_FILE%" echo %%~fV
            )
        )
    )
)

if "%DATASET_COUNT%"=="0" (
    echo No completed chunk vehicle folders were found under %RUN_ROOT%.
    exit /b 1
)

echo Training collected chunks:
echo Run root: %RUN_ROOT%
echo Dataset folders: %DATASET_COUNT%
echo Dataset file: %DATASET_FILE%
echo Init checkpoint: %INIT_CHECKPOINT%
echo Output checkpoint: %OUTPUT_CHECKPOINT%
echo Num workers: %NUM_WORKERS%
echo.

py -3.12 main.py train --init-checkpoint "%INIT_CHECKPOINT%" --dataset-file "%DATASET_FILE%" --output "%OUTPUT_CHECKPOINT%" --device %DEVICE% --epochs %EPOCHS% --batch-size %BATCH_SIZE% --num-workers %NUM_WORKERS% --learning-rate %LEARNING_RATE% --val-split %VAL_SPLIT% --log-interval %LOG_INTERVAL%
exit /b %ERRORLEVEL%
