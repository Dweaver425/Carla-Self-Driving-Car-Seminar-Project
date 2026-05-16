# Run Naming Scheme

Use short names with a version number:

```text
10hr2cars_v1
10hr2cars_v2
5hr2cars_v1
stopSigns_v1
quick2cars_v1
```

Keep the name lowercase/camelCase, avoid spaces, and only use letters, numbers,
underscores, and dashes. Bump `v1`, `v2`, `v3` when you repeat the same kind of
run.

## Folder Layout

Collection runs should live under:

```text
data\episodes\<run_name>\
  chunk_1\
    vehicle_01\
    vehicle_02\
  chunk_2\
    vehicle_01\
    vehicle_02\
```

TAR shards should live under:

```text
data\raw\<run_name>_tar_shards\
```

Models should use the same stem:

```text
models\<run_name>_cuda.pt
models\<run_name>_chunk_1_cuda.pt
```

Logs should use the same stem:

```text
logs\<run_name>_chunk_1_collect.log
logs\<run_name>_stop_sign_summary.json
```

## Examples

Collect a named 5-hour two-car shadow comparison:

```bat
set DURATION_HOURS=5&& scripts\collect_2car_shadow_compare_overnight_windows.bat models\10hr2cars_v1_cuda.pt 5hr2cars_v1
```

Train the raw chunks:

```bat
set LEARNING_RATE=0.00001&& set EPOCHS=2&& set BATCH_SIZE=512&& set NUM_WORKERS=10&& scripts\train_collected_chunks_fast_windows.bat data\episodes\5hr2cars_v1 models\10hr2cars_v1_cuda.pt models\5hr2cars_v1_cuda.pt
```

Package the run into TAR shards:

```bat
set MIN_IMAGES=75000&& set TARGET_IMAGES=150000&& scripts\package_collected_chunks_tar_shards_windows.bat data\episodes\5hr2cars_v1
```

Train from TAR shards:

```bat
set LEARNING_RATE=0.00001&& set EPOCHS=2&& set BATCH_SIZE=512&& set NUM_WORKERS=10&& scripts\train_tar_shards_fast_windows.bat data\raw\5hr2cars_v1_tar_shards\5hr2cars_v1_datasets.txt models\10hr2cars_v1_cuda.pt models\5hr2cars_v1_tar_cuda.pt
```

Run a targeted stop-sign comparison:

```bat
scripts\collect_stop_sign_targeted_compare_windows.bat models\5hr2cars_v1_cuda.pt stopSigns_v1
```

If a named folder already exists, the scripts stop and ask you to use the next
version name.
