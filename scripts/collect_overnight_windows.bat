@echo off
setlocal enabledelayedexpansion

rem Collects multiple CARLA autopilot episodes back-to-back so completed
rem segments stay usable even if the machine stops during the night.

set "RUNS=8"
set "STEPS_PER_RUN=50000"
set "OUTPUT_ROOT=data\episodes\carla_overnight_segments"
set "COMMON_ARGS=--backend carla --controller autopilot --quiet"

echo Starting overnight collection
echo Runs: %RUNS%
echo Steps per run: %STEPS_PER_RUN%
echo Output root: %OUTPUT_ROOT%
echo.

for /l %%I in (1,1,%RUNS%) do (
    set "SEGMENT=segment_%%I"
    echo [%%I/%RUNS%] Collecting !SEGMENT!...
    py -3.12 main.py collect %COMMON_ARGS% --steps %STEPS_PER_RUN% --output "%OUTPUT_ROOT%\!SEGMENT!"
    if errorlevel 1 (
        echo Collection stopped during !SEGMENT!.
        exit /b 1
    )
)

echo.
echo Overnight collection finished successfully.
exit /b 0
