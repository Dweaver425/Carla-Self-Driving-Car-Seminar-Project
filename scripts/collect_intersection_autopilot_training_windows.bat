@echo off
setlocal EnableExtensions

rem Collect targeted CARLA autopilot teacher data for the long spawn-1 intersection.
rem Usage:
rem   scripts\collect_intersection_autopilot_training_windows.bat models\current.pt intersectionAi_v2
rem Optional environment knobs:
rem   set RUNS=6
rem   set STEPS=7000
rem   set TARGET_SPEED=8
rem   set SPAWN_INDEX=1

set "CHECKPOINT=%~1"
set "RUN_NAME=%~2"
if "%RUN_NAME%"=="" set "RUN_NAME=intersectionAi_v2"
if "%HOST%"=="" set "HOST=127.0.0.1"
if "%PORT%"=="" set "PORT=2000"
if "%TM_PORT%"=="" set "TM_PORT=8000"
if "%SPAWN_INDEX%"=="" set "SPAWN_INDEX=1"
if "%STEPS%"=="" set "STEPS=6500"
if "%RUNS%"=="" set "RUNS=4"
if "%TARGET_SPEED%"=="" set "TARGET_SPEED=8"
if "%SPECTATOR%"=="" set "SPECTATOR=chase"
if "%LOG_DIR%"=="" set "LOG_DIR=logs"
if "%QUIET%"=="" set "QUIET=1"

if "%CHECKPOINT%"=="" (
    echo Missing checkpoint.
    echo Usage: scripts\collect_intersection_autopilot_training_windows.bat models\current.pt intersectionAi_v2
    exit /b 1
)
if not exist "%CHECKPOINT%" (
    echo Checkpoint not found: %CHECKPOINT%
    exit /b 1
)

set "RUN_ROOT=data\episodes\%RUN_NAME%"
set "DATASET_FILE=%LOG_DIR%\%RUN_NAME%_datasets.txt"
set "OUTPUT_CHECKPOINT=models\%RUN_NAME%_cuda.pt"

if exist "%RUN_ROOT%" (
    echo Run folder already exists: %RUN_ROOT%
    echo Use the next version name, for example intersectionAi_v3.
    exit /b 1
)
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
mkdir "%RUN_ROOT%"
type nul > "%DATASET_FILE%"

set "QUIET_FLAG="
if not "%QUIET%"=="0" set "QUIET_FLAG=--quiet"

echo Collecting targeted CARLA autopilot intersection data.
echo Checkpoint shadow: %CHECKPOINT%
echo Run root: %RUN_ROOT%
echo Dataset file: %DATASET_FILE%
echo Runs: %RUNS%
echo Steps per run: %STEPS%
echo.

call :collect_one 01 0.0 0.0
if errorlevel 1 exit /b 1
if %RUNS% GEQ 2 call :collect_one 02 0.5 0.0
if errorlevel 1 exit /b 1
if %RUNS% GEQ 3 call :collect_one 03 -0.5 0.0
if errorlevel 1 exit /b 1
if %RUNS% GEQ 4 call :collect_one 04 0.0 5.0
if errorlevel 1 exit /b 1
if %RUNS% GEQ 5 call :collect_one 05 0.0 -5.0
if errorlevel 1 exit /b 1
if %RUNS% GEQ 6 call :collect_one 06 0.75 5.0
if errorlevel 1 exit /b 1
if %RUNS% GEQ 7 call :collect_one 07 -0.75 -5.0
if errorlevel 1 exit /b 1
if %RUNS% GEQ 8 call :collect_one 08 1.0 0.0
if errorlevel 1 exit /b 1

if %RUNS% GTR 8 (
    echo RUNS above 8 requested; this script currently defines 8 route variations.
)

echo.
echo Collection complete.
echo Dataset file: %DATASET_FILE%
echo.
echo Suggested fine-tune command:
echo py -3.12 main.py train --init-checkpoint "%CHECKPOINT%" --dataset-file "%DATASET_FILE%" --output "%OUTPUT_CHECKPOINT%" --device cuda --epochs 3 --batch-size 512 --num-workers 10 --learning-rate 0.00001 --val-split 0.1 --log-interval 50
exit /b 0

:collect_one
set "RUN_ID=%~1"
set "LAT=%~2"
set "YAW=%~3"
set "RUN_OUT=%RUN_ROOT%\run_%RUN_ID%"

echo [%RUN_ID%/%RUNS%] spawn=%SPAWN_INDEX% lateral=%LAT% yaw=%YAW% output=%RUN_OUT%
py -3.12 main.py infer --backend carla --host "%HOST%" --port %PORT% --tm-port %TM_PORT% --checkpoint "%CHECKPOINT%" --steps %STEPS% --spawn-index %SPAWN_INDEX% --spawn-lateral-offset %LAT% --spawn-yaw-offset %YAW% --target-speed %TARGET_SPEED% --spectator %SPECTATOR% --autopilot-guide --output "%RUN_OUT%" %QUIET_FLAG%
if errorlevel 1 (
    echo Collection failed on run %RUN_ID%.
    exit /b 1
)
>> "%DATASET_FILE%" echo %RUN_OUT%
exit /b 0
