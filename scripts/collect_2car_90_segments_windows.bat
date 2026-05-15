@echo off
setlocal

rem 90-segment collect-only teacher/student run.
rem This uses the same stable pattern as the completed 96-chunk overnight run:
rem CARLA autopilot drives, the checkpoint predicts in shadow mode, and training
rem happens later from all completed chunk_* folders.

if "%RUN_LABEL%"=="" set "RUN_LABEL=model_shadow_2car_90seg"
if "%LOG_LABEL%"=="" set "LOG_LABEL=model_shadow_2car_90seg"
if "%VEHICLES%"=="" set "VEHICLES=2"
if "%SPAWN_INDICES%"=="" set "SPAWN_INDICES=1 29"
if "%STEPS%"=="" set "STEPS=2500"
if "%CHUNKS%"=="" set "CHUNKS=90"

call "%~dp0overnight_2car_collect_only_windows.bat" %*
