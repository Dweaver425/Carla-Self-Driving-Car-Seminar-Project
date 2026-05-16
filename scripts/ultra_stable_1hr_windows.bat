@echo off
setlocal

rem Lowest-risk 1-hour-ish preset.
rem Use this if the 6-car stable preset crashes or runs too hot.

set "RUN_LABEL=ultra1hr"
set "VEHICLES=3"
set "SPAWN_INDICES=1 15 29"
set "STEPS=3000"
set "ITERATIONS=8"
set "EPOCHS=1"
set "BATCH_SIZE=64"
set "NUM_WORKERS=0"

call "%~dp0stable_fleet_iterations_windows.bat" %*
