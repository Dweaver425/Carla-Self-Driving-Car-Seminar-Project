@echo off
setlocal

rem Lowest-risk overnight preset.
rem Smaller chunks mean less heat and easier recovery after a crash.

set "RUN_LABEL=ultra_overnight"
set "VEHICLES=3"
set "SPAWN_INDICES=1 15 29"
set "STEPS=3000"
set "ITERATIONS=48"
set "EPOCHS=1"
set "BATCH_SIZE=64"
set "NUM_WORKERS=0"

call "%~dp0stable_fleet_iterations_windows.bat" %*
