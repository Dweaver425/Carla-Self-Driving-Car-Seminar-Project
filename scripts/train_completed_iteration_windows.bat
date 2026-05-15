@echo off
if not "%CODEX_DELAYED_EXPANSION_READY%"=="1" (
    set "CODEX_DELAYED_EXPANSION_READY=1"
    cmd /v:on /c call "%~f0" %*
    exit /b %ERRORLEVEL%
)
setlocal EnableExtensions EnableDelayedExpansion

rem Trains from a completed collect-fleet iteration folder.
rem Usage:
rem   scripts\train_completed_iteration_windows.bat data\episodes\...\iteration_1 models\start.pt models\next.pt

set "ITERATION_DIR=%~1"
set "INIT_CHECKPOINT=%~2"
set "OUTPUT_CHECKPOINT=%~3"
if "%DEVICE%"=="" set "DEVICE=cuda"
if "%EPOCHS%"=="" set "EPOCHS=2"
if "%BATCH_SIZE%"=="" set "BATCH_SIZE=128"
if "%NUM_WORKERS%"=="" set "NUM_WORKERS=2"
if "%LEARNING_RATE%"=="" set "LEARNING_RATE=0.00005"
if "%VAL_SPLIT%"=="" set "VAL_SPLIT=0.1"
if "%LOG_INTERVAL%"=="" set "LOG_INTERVAL=100"
if "%LOG_DIR%"=="" set "LOG_DIR=logs"
set "DATASET_FILE=%LOG_DIR%\%~n3_datasets.txt"

if "%ITERATION_DIR%"=="" (
    echo Missing iteration folder.
    echo Usage: scripts\train_completed_iteration_windows.bat data\episodes\...\iteration_1 models\start.pt models\next.pt
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

if not exist "%ITERATION_DIR%\fleet_summary.json" (
    echo Missing fleet_summary.json under %ITERATION_DIR%.
    echo The collection may not be complete.
    exit /b 1
)
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
type nul > "%DATASET_FILE%"

set "DATASET_COUNT=0"
for /d %%D in ("%ITERATION_DIR%\vehicle_*") do (
    if exist "%%~fD\metadata.json" (
        set /a DATASET_COUNT+=1
        >> "%DATASET_FILE%" echo %%~fD
    )
)

if "%DATASET_COUNT%"=="0" (
    echo No completed vehicle_* folders were found under %ITERATION_DIR%.
    exit /b 1
)

echo Training completed iteration:
echo Iteration dir: %ITERATION_DIR%
echo Init checkpoint: %INIT_CHECKPOINT%
echo Output checkpoint: %OUTPUT_CHECKPOINT%
echo Dataset folders: %DATASET_COUNT%
echo Dataset file: %DATASET_FILE%
echo Batch size: %BATCH_SIZE%
echo Num workers: %NUM_WORKERS%
echo.

py -3.12 main.py train --init-checkpoint "%INIT_CHECKPOINT%" --dataset-file "%DATASET_FILE%" --output "%OUTPUT_CHECKPOINT%" --device %DEVICE% --epochs %EPOCHS% --batch-size %BATCH_SIZE% --num-workers %NUM_WORKERS% --learning-rate %LEARNING_RATE% --val-split %VAL_SPLIT% --log-interval %LOG_INTERVAL%
exit /b %ERRORLEVEL%
