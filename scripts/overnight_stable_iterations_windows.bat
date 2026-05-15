@echo off
setlocal

rem Conservative overnight preset.
rem Uses smaller chunks so a crash only loses the current iteration.
rem If temps are high, reduce VEHICLES to 4 before running.

set "RUN_LABEL=stable_overnight"
set "VEHICLES=6"
set "SPAWN_INDICES=1 8 15 22 29 36"
set "STEPS=6000"
set "ITERATIONS=24"
set "EPOCHS=2"
set "NUM_WORKERS=0"

call "%~dp0stable_fleet_iterations_windows.bat" %*
