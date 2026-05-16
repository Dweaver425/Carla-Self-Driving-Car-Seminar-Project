@echo off
setlocal

rem Package a chunk_* collection run into one TAR-backed dataset.
rem Usage:
rem   scripts\package_collected_chunks_tar_windows.bat data\episodes\10hr2cars_v1

set "RUN_ROOT=%~1"
set "DATASET_NAME=%~2"

if "%RUN_ROOT%"=="" (
    echo Missing run root.
    echo Usage: scripts\package_collected_chunks_tar_windows.bat data\episodes\10hr2cars_v1
    exit /b 1
)
if "%DATASET_NAME%"=="" set "DATASET_NAME=%~n1"

set "OUTPUT_ROOT=data\raw\%DATASET_NAME%_tar"
set "DATASET_ROOT=%OUTPUT_ROOT%\%DATASET_NAME%"
set "TAR_PATH=%OUTPUT_ROOT%\%DATASET_NAME%_images.tar"

echo Packaging collected chunks into TAR-backed dataset
echo Run root: %RUN_ROOT%
echo Dataset name: %DATASET_NAME%
echo Output root: %OUTPUT_ROOT%
echo TAR path: %TAR_PATH%
echo.

py -3.12 scripts\package_collected_chunks_tar.py --input-root "%RUN_ROOT%" --output-root "%OUTPUT_ROOT%" --dataset-name "%DATASET_NAME%" --overwrite
if errorlevel 1 exit /b %ERRORLEVEL%

py -3.12 scripts\build_tar_image_index.py --tar "%TAR_PATH%" --dataset-root "%DATASET_ROOT%" --dataset-name "%DATASET_NAME%" --overwrite
if errorlevel 1 exit /b %ERRORLEVEL%

echo.
echo TAR-backed dataset is ready:
echo %DATASET_ROOT%
echo.
echo Train with:
echo scripts\train_tar_dataset_fast_windows.bat "%DATASET_ROOT%" models\quick2cars_v1_chunk_1_cuda.pt models\%DATASET_NAME%_tar_cuda.pt
exit /b 0
