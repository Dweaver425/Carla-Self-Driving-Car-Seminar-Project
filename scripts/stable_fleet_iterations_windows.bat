@echo off
if not "%CODEX_DELAYED_EXPANSION_READY%"=="1" (
    set "CODEX_DELAYED_EXPANSION_READY=1"
    cmd /v:on /c call "%~f0" %*
    exit /b %ERRORLEVEL%
)
setlocal EnableExtensions EnableDelayedExpansion

rem Stable guided fleet iteration runner.
rem Wrappers set the duration/load. You may also run this directly.
rem Optional first argument: starting checkpoint path.

if "%HOST%"=="" set "HOST=127.0.0.1"
if "%PORT%"=="" set "PORT=2000"
if "%TM_PORT%"=="" set "TM_PORT=8000"
if "%VEHICLES%"=="" set "VEHICLES=6"
if "%STEPS%"=="" set "STEPS=6000"
if "%SPAWN_INDICES%"=="" set "SPAWN_INDICES=1 8 15 22 29 36"
if "%ITERATIONS%"=="" set "ITERATIONS=6"
if "%RUN_LABEL%"=="" set "RUN_LABEL=stable_fleet"
if "%DEVICE%"=="" set "DEVICE=cuda"
if "%EPOCHS%"=="" set "EPOCHS=2"
if "%BATCH_SIZE%"=="" set "BATCH_SIZE=128"
if "%NUM_WORKERS%"=="" set "NUM_WORKERS=0"
if "%LEARNING_RATE%"=="" set "LEARNING_RATE=0.00005"
if "%VAL_SPLIT%"=="" set "VAL_SPLIT=0.1"
if "%LOG_INTERVAL%"=="" set "LOG_INTERVAL=100"

set "CURRENT_CHECKPOINT=%~1"
if "%CURRENT_CHECKPOINT%"=="" (
    for /f "delims=" %%C in ('powershell -NoProfile -Command "$m=Get-ChildItem -Path models -File | Where-Object { ($_.Name -like 'carla_quick*_cuda.pt' -or $_.Name -like 'stable_*_cuda.pt' -or $_.Name -like 'ultra_*_cuda.pt') -and $_.Name -notlike '*_epoch_*' } | Sort-Object LastWriteTime -Descending | Select-Object -First 1; if ($m) { $m.FullName }"') do set "CURRENT_CHECKPOINT=%%C"
)
if "%CURRENT_CHECKPOINT%"=="" set "CURRENT_CHECKPOINT=models\carla_teacher_refined_cuda.pt"

for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "STAMP=%%I"
set "RUN_ROOT=data\episodes\%RUN_LABEL%_%STAMP%"
set "LOG_DIR=logs"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

echo Stable guided fleet iterations
echo Starting checkpoint: %CURRENT_CHECKPOINT%
echo Iterations: %ITERATIONS%
echo Vehicles: %VEHICLES%
echo Steps per iteration: %STEPS%
echo Epochs per iteration: %EPOCHS%
echo Num workers: %NUM_WORKERS%
echo Run root: %RUN_ROOT%
echo.
echo Approx disk use: each 10-car/6000-step run used about 1.55 GB.
echo This preset is smaller per round when VEHICLES is below 10.
echo.
echo Start CARLA first. Optional traffic terminal from the CARLA installation folder:
echo py -3.12 PythonAPI\examples\generate_traffic.py --host %HOST% --port %PORT% --tm-port %TM_PORT% --number-of-vehicles 30 --number-of-walkers 60 --safe
echo.
echo Press any key here to begin.
pause >nul

for /l %%I in (1,1,%ITERATIONS%) do (
    set "ITER_OUT=%RUN_ROOT%\iteration_%%I"
    set "NEXT_CHECKPOINT=models\%RUN_LABEL%_%STAMP%_iter_%%I_cuda.pt"
    set "COLLECT_LOG=%LOG_DIR%\%RUN_LABEL%_%STAMP%_iter_%%I_collect.log"
    set "TRAIN_LOG=%LOG_DIR%\%RUN_LABEL%_%STAMP%_iter_%%I_train.log"
    set "DATASET_FILE=%LOG_DIR%\%RUN_LABEL%_%STAMP%_iter_%%I_datasets.txt"
    set "RESUME_TRAIN=%LOG_DIR%\%RUN_LABEL%_%STAMP%_iter_%%I_resume_train.bat"

    type nul > "!DATASET_FILE!"
    for /l %%V in (1,1,%VEHICLES%) do (
        set "PAD=0%%V"
        set "VEHICLE_DIR=vehicle_!PAD:~-2!"
        >> "!DATASET_FILE!" echo !ITER_OUT!\!VEHICLE_DIR!
    )

    (
        echo @echo off
        echo cd /d "%CD%"
        echo py -3.12 main.py train --init-checkpoint "!CURRENT_CHECKPOINT!" --dataset-file "!DATASET_FILE!" --output "!NEXT_CHECKPOINT!" --device %DEVICE% --epochs %EPOCHS% --batch-size %BATCH_SIZE% --num-workers %NUM_WORKERS% --learning-rate %LEARNING_RATE% --val-split %VAL_SPLIT% --log-interval %LOG_INTERVAL%
    ) > "!RESUME_TRAIN!"

    echo.
    echo [%%I/%ITERATIONS%] Dataset file: !DATASET_FILE!
    echo [%%I/%ITERATIONS%] Resume command: !RESUME_TRAIN!
    echo [%%I/%ITERATIONS%] Collecting guided fleet data with !CURRENT_CHECKPOINT!
    py -3.12 main.py collect-fleet --backend carla --host %HOST% --port %PORT% --tm-port %TM_PORT% --vehicles %VEHICLES% --spawn-indices %SPAWN_INDICES% --steps %STEPS% --output-root "!ITER_OUT!" --checkpoint "!CURRENT_CHECKPOINT!" --target-speed 8 --lane-guard --traffic-rule-guard --quiet > "!COLLECT_LOG!" 2>&1
    if errorlevel 1 (
        echo Collection failed during iteration %%I.
        echo See log: !COLLECT_LOG!
        echo Training can be resumed, if the collection completed, with !RESUME_TRAIN!
        exit /b 1
    )

    echo [%%I/%ITERATIONS%] Summary: !ITER_OUT!\fleet_summary.json
    if exist "!ITER_OUT!" (
        copy /y "!DATASET_FILE!" "!ITER_OUT!\datasets.txt" >nul 2>&1
        copy /y "!RESUME_TRAIN!" "!ITER_OUT!\resume_train.bat" >nul 2>&1
    )
    echo [%%I/%ITERATIONS%] Fine-tuning to !NEXT_CHECKPOINT!
    py -3.12 main.py train --init-checkpoint "!CURRENT_CHECKPOINT!" --dataset-file "!DATASET_FILE!" --output "!NEXT_CHECKPOINT!" --device %DEVICE% --epochs %EPOCHS% --batch-size %BATCH_SIZE% --num-workers %NUM_WORKERS% --learning-rate %LEARNING_RATE% --val-split %VAL_SPLIT% --log-interval %LOG_INTERVAL% > "!TRAIN_LOG!" 2>&1
    if errorlevel 1 (
        echo Training failed during iteration %%I.
        echo See log: !TRAIN_LOG!
        echo Completed collection can be resumed with scripts\train_completed_iteration_windows.bat.
        exit /b 1
    )

    set "CURRENT_CHECKPOINT=!NEXT_CHECKPOINT!"
)

echo.
echo Stable fleet iterations finished.
echo Final checkpoint: !CURRENT_CHECKPOINT!
exit /b 0
