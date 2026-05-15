@echo off
setlocal enabledelayedexpansion

rem Collects multiple CARLA autopilot teacher vehicles at the same time.
rem Start CARLA first. Optional: start generate_traffic.py in another terminal.

set "HOST=127.0.0.1"
set "PORT=2000"
set "TM_PORT=8000"
set "VEHICLES=3"
set "STEPS=360000"
set "SPAWN_INDICES=1 8 15"
set "CHECKPOINT=models\carla_teacher_refined_cuda.pt"

for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "STAMP=%%I"
set "OUTPUT_ROOT=data\episodes\carla_fleet_overnight_!STAMP!"

echo Multi-car CARLA overnight collection
echo Vehicles: %VEHICLES%
echo Steps: %STEPS%
echo Current model: %CHECKPOINT%
echo Output root: %OUTPUT_ROOT%
echo.
echo This records one episode folder per vehicle:
echo   %OUTPUT_ROOT%\vehicle_01
echo   %OUTPUT_ROOT%\vehicle_02
echo   %OUTPUT_ROOT%\vehicle_03
echo.
echo Optional traffic terminal, from the CARLA installation folder:
echo py -3.12 PythonAPI\examples\generate_traffic.py --host %HOST% --port %PORT% --tm-port %TM_PORT% --number-of-vehicles 30 --number-of-walkers 60 --safe
echo.
echo Keep CARLA running, then press any key here to start fleet collection.
pause >nul

py -3.12 main.py collect-fleet --backend carla --host %HOST% --port %PORT% --tm-port %TM_PORT% --vehicles %VEHICLES% --spawn-indices %SPAWN_INDICES% --steps %STEPS% --output-root "%OUTPUT_ROOT%" --checkpoint "%CHECKPOINT%" --target-speed 8 --lane-guard --traffic-rule-guard --quiet
if errorlevel 1 (
    echo Fleet collection failed or was stopped.
    exit /b 1
)

echo.
echo Fleet collection finished successfully.
echo Output root: %OUTPUT_ROOT%
exit /b 0
