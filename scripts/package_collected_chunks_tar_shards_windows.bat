@echo off
setlocal

rem Package a chunk_* collection run into TAR-backed shards.
rem Default shard target is 100,000 images, with a 50,000-image minimum.
rem Usage:
rem   scripts\package_collected_chunks_tar_shards_windows.bat data\episodes\10hr2cars_v1
rem   scripts\package_collected_chunks_tar_shards_windows.bat data\episodes\old_long_name 10hr2cars_v1

set "RUN_ROOT=%~1"
set "DATASET_NAME=%~2"

if "%RUN_ROOT%"=="" (
    echo Missing run root.
    echo Usage: scripts\package_collected_chunks_tar_shards_windows.bat data\episodes\10hr2cars_v1
    exit /b 1
)
if "%DATASET_NAME%"=="" set "DATASET_NAME=%~n1"

if "%MIN_IMAGES%"=="" set "MIN_IMAGES=50000"
if "%TARGET_IMAGES%"=="" set "TARGET_IMAGES=100000"

set "OUTPUT_ROOT=data\raw\%DATASET_NAME%_tar_shards"
set "DATASET_FILE=%OUTPUT_ROOT%\%DATASET_NAME%_datasets.txt"

echo Packaging collected chunks into TAR-backed shards
echo Run root: %RUN_ROOT%
echo Dataset name: %DATASET_NAME%
echo Output root: %OUTPUT_ROOT%
echo Min images per shard: %MIN_IMAGES%
echo Target images per shard: %TARGET_IMAGES%
echo.

py -3.12 scripts\package_collected_chunks_tar_shards.py --input-root "%RUN_ROOT%" --output-root "%OUTPUT_ROOT%" --dataset-name "%DATASET_NAME%" --min-images %MIN_IMAGES% --target-images %TARGET_IMAGES% --overwrite
if errorlevel 1 exit /b %ERRORLEVEL%

echo.
echo TAR shard dataset file is ready:
echo %DATASET_FILE%
echo.
echo Train with:
echo scripts\train_tar_shards_fast_windows.bat "%DATASET_FILE%" models\quick2cars_v1_chunk_1_cuda.pt models\%DATASET_NAME%_tar_shards_cuda.pt
exit /b 0
