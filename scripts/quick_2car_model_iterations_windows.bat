@echo off
setlocal

rem Short teacher-student iteration preset.
rem CARLA autopilot drives, the checkpoint predicts in shadow mode, then the
rem checkpoint is fine-tuned from the collected CARLA labels.

set "RUN_LABEL=quick_2car_iter"
set "VEHICLES=2"
set "SPAWN_INDICES=1 29"
set "STEPS=2500"
set "ITERATIONS=3"
set "EPOCHS=1"
set "BATCH_SIZE=64"
set "NUM_WORKERS=0"

call "%~dp0stable_fleet_iterations_windows.bat" %*
