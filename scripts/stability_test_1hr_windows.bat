@echo off
setlocal

rem About a 1-hour stability test on a typical desktop.
rem Lower heat than the 10-car stress loop, but still useful for model improvement.

set "RUN_LABEL=stable_1hr"
set "VEHICLES=6"
set "SPAWN_INDICES=1 8 15 22 29 36"
set "STEPS=6000"
set "ITERATIONS=6"
set "EPOCHS=2"
set "NUM_WORKERS=0"

call "%~dp0stable_fleet_iterations_windows.bat" %*
