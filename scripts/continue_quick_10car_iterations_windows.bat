@echo off
if "%CODEX_DELAYED_EXPANSION_READY%"=="1" goto delayed_ready
set "CODEX_DELAYED_EXPANSION_READY=1"
cmd /v:on /c call "%~f0" %*
exit /b %ERRORLEVEL%

:delayed_ready
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
    for /f "delims=" %%C in ('powershell -NoProfile -Command "$patterns='10hr2cars*_cuda.pt','5hr2cars*_cuda.pt','shadow2cars*_cuda.pt','overnight2cars*_cuda.pt','quick10cars*_cuda.pt','quick2cars*_cuda.pt','stable1hr*_cuda.pt','ultra1hr*_cuda.pt','ultraOvernight*_cuda.pt','stopSigns*_cuda.pt','teacherRefined*_cuda.pt'; $m=Get-ChildItem -Path models -File | Where-Object { $n=$_.Name; ($patterns | Where-Object { $n -like $_ }) -and $n -notlike '*_epoch_*' } | Sort-Object LastWriteTime -Descending | Select-Object -First 1; if ($m) { $m.FullName }"') do set "CURRENT_CHECKPOINT=%%C"
)
if "%CURRENT_CHECKPOINT%"=="" set "CURRENT_CHECKPOINT=models\teacherRefined_v1_cuda.pt"

for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "STAMP=%%I"
set "ARG_RUN_NAME=%~2"
if not "%ARG_RUN_NAME%"=="" set "RUN_NAME=%ARG_RUN_NAME%"
if "%RUN_NAME%"=="" set "RUN_NAME=quick10carsContinue_!STAMP!"
set "RUN_ROOT=data\episodes\%RUN_NAME%"
set "LOG_DIR=logs"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
if exist "%RUN_ROOT%" (
    echo Run root already exists: %RUN_ROOT%
    echo Use a new version name, for example quick10carsContinue_v2.
    exit /b 1
)

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
    set "ITER_OUT=!RUN_ROOT!\chunk_%%I"
    set "NEXT_CHECKPOINT=models\%RUN_NAME%_chunk_%%I_cuda.pt"
    set "COLLECT_LOG=%LOG_DIR%\%RUN_NAME%_chunk_%%I_collect.log"
    set "TRAIN_LOG=%LOG_DIR%\%RUN_NAME%_chunk_%%I_train.log"

    echo.
    echo [%%I/%ITERATIONS%] Collecting 10-car comparison with !CURRENT_CHECKPOINT!
    py -3.12 main.py collect-fleet --backend carla --host %HOST% --port %PORT% --tm-port %TM_PORT% --vehicles %VEHICLES% --spawn-indices %SPAWN_INDICES% --steps %STEPS% --output-root "!ITER_OUT!" --checkpoint "!CURRENT_CHECKPOINT!" --target-speed 8 --lane-guard --traffic-rule-guard --quiet > "!COLLECT_LOG!" 2>&1
    if errorlevel 1 (
        echo Collection failed during chunk %%I.
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
        echo Training failed during chunk %%I.
        echo See log: !TRAIN_LOG!
        exit /b 1
    )

    set "CURRENT_CHECKPOINT=!NEXT_CHECKPOINT!"
)

echo.
echo Quick continuation finished.
echo Final checkpoint: !CURRENT_CHECKPOINT!
exit /b 0
