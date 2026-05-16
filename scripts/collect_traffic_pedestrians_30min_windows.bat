@echo off
setlocal enabledelayedexpansion

rem Collects one 30-sim-minute CARLA episode with background vehicles and pedestrians.
rem Start CARLA first. Then start CARLA's generate_traffic.py in another terminal.

set "HOST=127.0.0.1"
set "PORT=2000"
set "TM_PORT=8000"
set "VEHICLES=30"
set "WALKERS=60"
set "STEPS=36000"
set "SPAWN_INDEX=1"
set "TARGET_SPEED=8"
set "CHECKPOINT=models\weekendTarIndex_v1_cuda.pt"

for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "STAMP=%%I"
set "OUTPUT=data\episodes\trafficPed30min_v1_!STAMP!"

echo 30 simulated minutes = %STEPS% steps at fixed_delta_seconds 0.05.
echo.
echo If generate_traffic.py says "No module named carla", run this once from the CARLA folder:
echo py -3.12 -m pip install PythonAPI\carla\dist\carla-0.9.16-cp312-cp312-win_amd64.whl
echo.
echo Terminal 1, from the CARLA installation folder:
echo py -3.12 PythonAPI\examples\generate_traffic.py --host %HOST% --port %PORT% --tm-port %TM_PORT% --number-of-vehicles %VEHICLES% --number-of-walkers %WALKERS% --safe
echo.
echo Keep that traffic terminal running, then press any key here to start collection.
pause >nul

echo.
echo Collecting guided traffic/pedestrian episode:
echo Output: %OUTPUT%
echo.

py -3.12 main.py infer --backend carla --checkpoint "%CHECKPOINT%" --steps %STEPS% --spawn-index %SPAWN_INDEX% --target-speed %TARGET_SPEED% --spectator chase --autopilot-guide --output "%OUTPUT%" --quiet
if errorlevel 1 (
    echo Collection failed or was stopped.
    exit /b 1
)

echo.
echo Collection finished successfully.
echo Output: %OUTPUT%
exit /b 0
