@echo off
setlocal

rem Find spawn points that approach stop signs, then run the normal stop-sign
rem comparison workflow from those targeted starts. CARLA needs to already be
rem open on the configured host/port.

if "%HOST%"=="" set "HOST=127.0.0.1"
if "%PORT%"=="" set "PORT=2000"
if "%VEHICLES%"=="" set "VEHICLES=2"
if "%STEPS%"=="" set "STEPS=15000"
if "%STOP_LOOKAHEAD_M%"=="" set "STOP_LOOKAHEAD_M=160"
if "%STOP_NEAR_M%"=="" set "STOP_NEAR_M=12"
set "CURRENT_CHECKPOINT=%~1"

if "%CURRENT_CHECKPOINT%"=="" (
    echo Missing model checkpoint.
    echo Usage: scripts\collect_stop_sign_targeted_compare_windows.bat models\your_model.pt
    exit /b 1
)

echo Finding stop-sign spawn indices...
for /f "delims=" %%S in ('py -3.12 scripts\find_stop_sign_spawn_indices.py --host %HOST% --port %PORT% --count %VEHICLES% --lookahead-m %STOP_LOOKAHEAD_M% --near-m %STOP_NEAR_M% --format plain ^| findstr /R "^[0-9][0-9 ]*$"') do set "SPAWN_INDICES=%%S"

if "%SPAWN_INDICES%"=="" (
    echo Could not find stop-sign spawn indices in the current CARLA world.
    echo Try:
    echo py -3.12 scripts\find_stop_sign_spawn_indices.py --count 10 --format json
    exit /b 1
)

echo Spawn indices: %SPAWN_INDICES%
echo.
call scripts\collect_stop_sign_compare_windows.bat "%CURRENT_CHECKPOINT%"
exit /b %ERRORLEVEL%
