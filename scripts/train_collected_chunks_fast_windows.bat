@echo off
setlocal

rem Fast training preset for high-end CUDA systems.
rem Uses a larger batch and more data-loader workers for huge collected runs.
rem If Windows or the disk gets unstable, lower NUM_WORKERS to 8 or 4.

if "%DEVICE%"=="" set "DEVICE=cuda"
if "%EPOCHS%"=="" set "EPOCHS=2"
if "%BATCH_SIZE%"=="" set "BATCH_SIZE=512"
if "%NUM_WORKERS%"=="" set "NUM_WORKERS=10"
if "%LOG_INTERVAL%"=="" set "LOG_INTERVAL=50"

call "%~dp0train_collected_chunks_windows.bat" %*
