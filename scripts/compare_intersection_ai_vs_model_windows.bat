@echo off
setlocal EnableExtensions

rem Record one CARLA autopilot teacher run and one model run, then compare
rem how many frames each spends inside junctions.
rem Usage:
rem   scripts\compare_intersection_ai_vs_model_windows.bat models\current.pt intersectionCompare_v1

set "CHECKPOINT=%~1"
set "RUN_NAME=%~2"
if "%RUN_NAME%"=="" set "RUN_NAME=intersectionCompare_v1"
if "%HOST%"=="" set "HOST=127.0.0.1"
if "%PORT%"=="" set "PORT=2000"
if "%TM_PORT%"=="" set "TM_PORT=8000"
if "%SPAWN_INDEX%"=="" set "SPAWN_INDEX=1"
if "%STEPS%"=="" set "STEPS=7000"
if "%TARGET_SPEED%"=="" set "TARGET_SPEED=8"
if "%SPECTATOR%"=="" set "SPECTATOR=chase"
if "%LOG_DIR%"=="" set "LOG_DIR=logs"
if "%QUIET%"=="" set "QUIET=1"

if "%CHECKPOINT%"=="" (
    echo Missing checkpoint.
    echo Usage: scripts\compare_intersection_ai_vs_model_windows.bat models\current.pt intersectionCompare_v1
    exit /b 1
)
if not exist "%CHECKPOINT%" (
    echo Checkpoint not found: %CHECKPOINT%
    exit /b 1
)

set "RUN_ROOT=data\episodes\%RUN_NAME%"
set "TEACHER_OUT=%RUN_ROOT%\teacher"
set "MODEL_OUT=%RUN_ROOT%\model"
set "COMPARE_JSON=%LOG_DIR%\%RUN_NAME%_intersection_compare.json"
set "TEACHER_DATASET=%LOG_DIR%\%RUN_NAME%_teacher_datasets.txt"
set "OUTPUT_CHECKPOINT=models\%RUN_NAME%_cuda.pt"
set "REUSE_TEACHER=0"
set "REUSE_MODEL=0"

if exist "%RUN_ROOT%" (
    if not exist "%TEACHER_OUT%\metadata.json" (
        echo Run folder already exists without a completed teacher episode: %RUN_ROOT%
        echo Use the next version name, for example intersectionCompare_v3.
        exit /b 1
    )
    findstr /C:"\"status\": \"completed\"" "%TEACHER_OUT%\metadata.json" >nul
    if errorlevel 1 (
        echo Existing teacher episode is not completed: %TEACHER_OUT%
        exit /b 1
    )
    set "REUSE_TEACHER=1"

    if exist "%MODEL_OUT%\metadata.json" (
        findstr /C:"\"status\": \"completed\"" "%MODEL_OUT%\metadata.json" >nul
        if errorlevel 1 (
            echo Existing model episode is not completed: %MODEL_OUT%
            exit /b 1
        )
        set "REUSE_MODEL=1"
    )
)
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

set "QUIET_FLAG="
if not "%QUIET%"=="0" set "QUIET_FLAG=--quiet"

if "%REUSE_TEACHER%"=="1" (
    echo Reusing completed CARLA teacher run: %TEACHER_OUT%
) else (
    echo Recording CARLA teacher intersection run...
    py -3.12 main.py infer --backend carla --host "%HOST%" --port %PORT% --tm-port %TM_PORT% --checkpoint "%CHECKPOINT%" --steps %STEPS% --spawn-index %SPAWN_INDEX% --target-speed %TARGET_SPEED% --spectator %SPECTATOR% --autopilot-guide --output "%TEACHER_OUT%" %QUIET_FLAG%
    if errorlevel 1 (
        findstr /C:"\"status\": \"completed\"" "%TEACHER_OUT%\metadata.json" >nul 2>nul
        if errorlevel 1 (
            echo Teacher run failed before completion.
            exit /b 1
        )
        echo Teacher command returned a nonzero code, but metadata is completed; continuing.
    )
)

echo.
if "%REUSE_MODEL%"=="1" (
    echo Reusing completed model run: %MODEL_OUT%
) else (
    echo Recording model intersection run with lane and traffic-rule guards...
    py -3.12 main.py infer --backend carla --host "%HOST%" --port %PORT% --tm-port %TM_PORT% --checkpoint "%CHECKPOINT%" --steps %STEPS% --spawn-index %SPAWN_INDEX% --target-speed %TARGET_SPEED% --spectator %SPECTATOR% --lane-guard --traffic-rule-guard --output "%MODEL_OUT%" %QUIET_FLAG%
    if errorlevel 1 (
        findstr /C:"\"status\": \"completed\"" "%MODEL_OUT%\metadata.json" >nul 2>nul
        if errorlevel 1 (
            echo Model run failed before completion.
            exit /b 1
        )
        echo Model command returned a nonzero code, but metadata is completed; continuing.
    )
)

echo.
echo Comparing junction frames...
py -3.12 scripts\analyze_intersection_frames.py --teacher-root "%TEACHER_OUT%" --model-root "%MODEL_OUT%" --output-json "%COMPARE_JSON%" --write-teacher-dataset "%TEACHER_DATASET%"
if errorlevel 1 exit /b 1

echo.
echo Comparison JSON: %COMPARE_JSON%
echo Teacher dataset file: %TEACHER_DATASET%
echo.
echo Suggested fine-tune command:
echo py -3.12 main.py train --init-checkpoint "%CHECKPOINT%" --dataset-file "%TEACHER_DATASET%" --output "%OUTPUT_CHECKPOINT%" --device cuda --epochs 2 --batch-size 512 --num-workers 10 --learning-rate 0.00001 --val-split 0.1 --log-interval 50
exit /b 0
