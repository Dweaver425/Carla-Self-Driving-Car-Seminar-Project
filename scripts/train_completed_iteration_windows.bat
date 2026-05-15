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
set "DEVICE=cuda"
set "EPOCHS=2"
set "BATCH_SIZE=128"
set "NUM_WORKERS=0"
set "LEARNING_RATE=0.00005"
set "VAL_SPLIT=0.1"
set "LOG_INTERVAL=100"

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

set "DATASETS="
set "DATASET_COUNT=0"
for /d %%D in ("%ITERATION_DIR%\vehicle_*") do (
    if exist "%%~fD\metadata.json" (
        set /a DATASET_COUNT+=1
        set DATASETS=!DATASETS! "%%~fD"
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
echo Num workers: %NUM_WORKERS%
echo.

py -3.12 main.py train --init-checkpoint "%INIT_CHECKPOINT%" --dataset %DATASETS% --output "%OUTPUT_CHECKPOINT%" --device %DEVICE% --epochs %EPOCHS% --batch-size %BATCH_SIZE% --num-workers %NUM_WORKERS% --learning-rate %LEARNING_RATE% --val-split %VAL_SPLIT% --log-interval %LOG_INTERVAL%
exit /b %ERRORLEVEL%
