@echo off
setlocal EnableExtensions

rem Build a completed-episode file from data\episodes, then package those
rem raw episodes into TAR-backed shards under data\tar_shards.
rem Raw data is not deleted by this script.

if "%DATASET_NAME%"=="" set "DATASET_NAME=all_raw"
if "%EPISODE_ROOT%"=="" set "EPISODE_ROOT=data\episodes"
if "%OUTPUT_BASE%"=="" set "OUTPUT_BASE=data\tar_shards"
if "%MIN_IMAGES%"=="" set "MIN_IMAGES=50000"
if "%TARGET_IMAGES%"=="" set "TARGET_IMAGES=100000"

set "EPISODE_FILE=%OUTPUT_BASE%\%DATASET_NAME%_completed_episodes.txt"
set "EPISODE_SUMMARY=%OUTPUT_BASE%\%DATASET_NAME%_completed_episodes_summary.json"
set "OUTPUT_ROOT=%OUTPUT_BASE%\%DATASET_NAME%_tar_shards"
set "DATASET_FILE=%OUTPUT_ROOT%\%DATASET_NAME%_datasets.txt"

echo Packaging all completed raw episodes into TAR shards
echo Dataset name: %DATASET_NAME%
echo Episode root: %EPISODE_ROOT%
echo Episode file: %EPISODE_FILE%
echo Output root: %OUTPUT_ROOT%
echo Min images per shard: %MIN_IMAGES%
echo Target images per shard: %TARGET_IMAGES%
echo.
echo Raw data under %EPISODE_ROOT% will not be deleted.
echo.

if not exist "%OUTPUT_BASE%" mkdir "%OUTPUT_BASE%"

call py -3.12 scripts\build_completed_episode_file.py --episode-root "%EPISODE_ROOT%" --output "%EPISODE_FILE%" --summary-output "%EPISODE_SUMMARY%"
if errorlevel 1 exit /b %ERRORLEVEL%

echo.
echo Episode inventory ready. Starting TAR shard packaging...
echo This can take a long time for multi-million-frame datasets.
echo.

call py -3.12 scripts\package_episode_folders_tar_shards.py --episode-root "%EPISODE_ROOT%" --episode-file "%EPISODE_FILE%" --output-root "%OUTPUT_ROOT%" --dataset-name "%DATASET_NAME%" --min-images %MIN_IMAGES% --target-images %TARGET_IMAGES% --overwrite
if errorlevel 1 exit /b %ERRORLEVEL%

echo.
echo TAR shard dataset file is ready:
echo %DATASET_FILE%
echo.
echo Use this dataset file for TAR-shard training:
echo scripts\train_tar_shards_fast_windows.bat "%DATASET_FILE%" models\final_project_cuda.pt models\research_all_raw_tar_cuda.pt
exit /b 0
