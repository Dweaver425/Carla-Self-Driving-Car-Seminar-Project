@echo off
setlocal

rem Package selected flat data\episodes folders into TAR-backed shards.
rem The episode file should contain one folder name or path per line.
rem Usage:
rem   scripts\package_episode_folders_tar_shards_windows.bat early_guided logs\early_guided_episodes.txt

set "DATASET_NAME=%~1"
set "EPISODE_FILE=%~2"

if "%DATASET_NAME%"=="" (
    echo Missing dataset name.
    echo Usage: scripts\package_episode_folders_tar_shards_windows.bat early_guided logs\early_guided_episodes.txt
    exit /b 1
)
if "%EPISODE_FILE%"=="" (
    echo Missing episode list file.
    echo Usage: scripts\package_episode_folders_tar_shards_windows.bat early_guided logs\early_guided_episodes.txt
    exit /b 1
)

if "%EPISODE_ROOT%"=="" set "EPISODE_ROOT=data\episodes"
if "%MIN_IMAGES%"=="" set "MIN_IMAGES=50000"
if "%TARGET_IMAGES%"=="" set "TARGET_IMAGES=100000"

set "OUTPUT_ROOT=data\raw\%DATASET_NAME%_tar_shards"
set "DATASET_FILE=%OUTPUT_ROOT%\%DATASET_NAME%_datasets.txt"

echo Packaging selected episode folders into TAR-backed shards
echo Dataset name: %DATASET_NAME%
echo Episode root: %EPISODE_ROOT%
echo Episode file: %EPISODE_FILE%
echo Output root: %OUTPUT_ROOT%
echo Min images per shard: %MIN_IMAGES%
echo Target images per shard: %TARGET_IMAGES%
echo.

py -3.12 scripts\package_episode_folders_tar_shards.py --episode-root "%EPISODE_ROOT%" --episode-file "%EPISODE_FILE%" --output-root "%OUTPUT_ROOT%" --dataset-name "%DATASET_NAME%" --min-images %MIN_IMAGES% --target-images %TARGET_IMAGES% --overwrite
if errorlevel 1 exit /b %ERRORLEVEL%

echo.
echo TAR shard dataset file is ready:
echo %DATASET_FILE%
exit /b 0
