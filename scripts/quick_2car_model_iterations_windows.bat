@echo off
setlocal

rem Short teacher-student iteration preset.
rem CARLA autopilot drives, the checkpoint predicts in shadow mode, then the
rem checkpoint is fine-tuned from the collected CARLA labels.

if "%RUN_LABEL%"=="" set "RUN_LABEL=quick2cars"
if "%VEHICLES%"=="" set "VEHICLES=2"
if "%SPAWN_INDICES%"=="" set "SPAWN_INDICES=1 29"
if "%STEPS%"=="" set "STEPS=2500"
if "%ITERATIONS%"=="" set "ITERATIONS=3"
if "%EPOCHS%"=="" set "EPOCHS=1"
if "%BATCH_SIZE%"=="" set "BATCH_SIZE=64"
if "%NUM_WORKERS%"=="" set "NUM_WORKERS=2"

call "%~dp0stable_fleet_iterations_windows.bat" %*
