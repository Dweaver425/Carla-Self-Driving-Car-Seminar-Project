@echo off
setlocal

rem Train directly from the TAR image index. This avoids extracting millions of
rem tiny PNG files into the Windows filesystem.

set "DATASET=data\raw\carla_weekend_combined\carla_weekend_combined"
set "OUTPUT=models\carla_weekend_tar_index_cuda.pt"
set "DEVICE=cuda"
set "EPOCHS=4"
set "BATCH_SIZE=256"
set "NUM_WORKERS=8"
set "VAL_SPLIT=0.1"
set "LOG_INTERVAL=100"

.\.venv\Scripts\python.exe -u main.py train --dataset "%DATASET%" --output "%OUTPUT%" --device %DEVICE% --epochs %EPOCHS% --batch-size %BATCH_SIZE% --num-workers %NUM_WORKERS% --val-split %VAL_SPLIT% --log-interval %LOG_INTERVAL%
