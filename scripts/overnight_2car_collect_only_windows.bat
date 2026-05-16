@echo off
if "%CODEX_DELAYED_EXPANSION_READY%"=="1" goto delayed_ready
set "CODEX_DELAYED_EXPANSION_READY=1"
cmd /v:on /c call "%~f0" %*
exit /b %ERRORLEVEL%

:delayed_ready
setlocal EnableExtensions EnableDelayedExpansion

rem Most reliable segmented collection mode:
rem - CARLA autopilot teacher cars drive
rem - the current checkpoint predicts in shadow mode for comparison
rem - short chunks keep each saved segment recoverable
rem - collection only, no training inside the loop
rem Train the completed chunks afterward.

if "%HOST%"=="" set "HOST=127.0.0.1"
if "%PORT%"=="" set "PORT=2000"
if "%TM_PORT%"=="" set "TM_PORT=8000"
if "%VEHICLES%"=="" set "VEHICLES=2"
if "%SPAWN_INDICES%"=="" set "SPAWN_INDICES=1 29"
if "%STEPS%"=="" set "STEPS=2500"
if "%CHUNKS%"=="" set "CHUNKS=96"
if "%RUN_LABEL%"=="" set "RUN_LABEL=overnight2cars"
set "CURRENT_CHECKPOINT=%~1"
set "ARG_RUN_NAME=%~2"
if not "%ARG_RUN_NAME%"=="" set "RUN_NAME=%ARG_RUN_NAME%"

if "%CURRENT_CHECKPOINT%"=="" (
    for /f "delims=" %%C in ('powershell -NoProfile -Command "$patterns='10hr2cars*_cuda.pt','5hr2cars*_cuda.pt','shadow2cars*_cuda.pt','overnight2cars*_cuda.pt','quick10cars*_cuda.pt','quick2cars*_cuda.pt','stable1hr*_cuda.pt','ultra1hr*_cuda.pt','ultraOvernight*_cuda.pt','stopSigns*_cuda.pt','teacherRefined*_cuda.pt'; $m=Get-ChildItem -Path models -File | Where-Object { $n=$_.Name; ($patterns | Where-Object { $n -like $_ }) -and $n -notlike '*_epoch_*' } | Sort-Object LastWriteTime -Descending | Select-Object -First 1; if ($m) { $m.FullName }"') do set "CURRENT_CHECKPOINT=%%C"
)
if "%CURRENT_CHECKPOINT%"=="" set "CURRENT_CHECKPOINT=models\teacherRefined_v1_cuda.pt"

for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "STAMP=%%I"
if "%RUN_NAME%"=="" set "RUN_NAME=%RUN_LABEL%_%STAMP%"
if "%LOG_LABEL%"=="" set "LOG_LABEL=%RUN_NAME%"
set "RUN_ROOT=data\episodes\%RUN_NAME%"
set "LOG_DIR=logs"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
if exist "%RUN_ROOT%" (
    echo Run root already exists: %RUN_ROOT%
    echo Use a new version name, for example 10hr2cars_v2.
    exit /b 1
)

echo Segmented collect-only mode
echo Checkpoint: %CURRENT_CHECKPOINT%
echo Run name: %RUN_NAME%
echo Chunks: %CHUNKS%
echo Vehicles: %VEHICLES%
echo Steps per chunk: %STEPS%
echo Run root: %RUN_ROOT%
echo.
echo This does not train during the overnight loop. Train completed chunks later.
echo Press any key to start.
pause >nul

for /l %%I in (1,1,%CHUNKS%) do (
    echo.
    echo [%%I/%CHUNKS%] Collecting %RUN_ROOT%\chunk_%%I
    py -3.12 main.py collect-fleet --backend carla --host %HOST% --port %PORT% --tm-port %TM_PORT% --vehicles %VEHICLES% --spawn-indices %SPAWN_INDICES% --steps %STEPS% --output-root "%RUN_ROOT%\chunk_%%I" --checkpoint "%CURRENT_CHECKPOINT%" --target-speed 8 --lane-guard --traffic-rule-guard --quiet > "%LOG_DIR%\%LOG_LABEL%_chunk_%%I_collect.log" 2>&1
    if errorlevel 1 (
        echo Collection failed during chunk %%I.
        echo See log: %LOG_DIR%\%LOG_LABEL%_chunk_%%I_collect.log
        exit /b 1
    )
)

echo.
echo Segmented collection finished.
echo Run root: %RUN_ROOT%
echo Train later with:
echo scripts\train_collected_chunks_windows.bat %RUN_ROOT% "%CURRENT_CHECKPOINT%" models\%RUN_NAME%_cuda.pt
exit /b 0
