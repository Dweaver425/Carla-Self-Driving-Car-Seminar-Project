@echo off
setlocal

rem Lowest-risk overnight preset.
rem Smaller chunks mean less heat and easier recovery after a crash.

set "RUN_LABEL=ultraOvernight"
set "VEHICLES=2"
set "SPAWN_INDICES=1 29"
set "STEPS=2500"
set "ITERATIONS=48"
set "EPOCHS=1"
set "BATCH_SIZE=64"
set "NUM_WORKERS=0"

call "%~dp0stable_fleet_iterations_windows.bat" %*
