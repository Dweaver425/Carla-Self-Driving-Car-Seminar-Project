# CLI Command Reference

This file explains every command in the project in plain language while still keeping the full parameter list.

## The Main Rule

This project prefers `py -3.12` in command examples so the Python version is explicit and consistent.

- On Windows, use `py -3.12`
- On macOS or Linux, replace `py -3.12` with `python3`

On Windows, the repo includes `py.cmd` so this command style works from the
project folder even if the global Windows Python Launcher is missing. The shim
runs `.venv\Scripts\python.exe`, which is the environment that has the project
dependencies installed.

You normally run the project through one file:

```bash
py -3.12 main.py <command> [options]
```

## What Each Command Means

| Command | Simple meaning | When to use it |
| --- | --- | --- |
| `env` | Check your Python environment | Use first, before running anything else |
| `demo` | Drive without saving data | Use for quick testing |
| `collect` | Save a driving dataset | Use before training |
| `train` | Train the driving model | Use after collecting data |
| `infer` | Let a trained checkpoint or CARLA autopilot drive | Use to test driving behavior |
| `serve` | Start the fleet server | Use when vehicles should publish telemetry |

## Command Section Format

Every command section in this document uses the same pattern:

- What it does
- Good time to use it
- Base command
- Parameters
- Example commands
- Output to check when that matters

## Important Command Behavior

- If you run `py -3.12 main.py` with no command, the project starts `demo`.
- If you run `py -3.12 main.py --some-flag`, the project also treats that as `demo`.
- That means `py -3.12 main.py --help` behaves like `demo --help`.

## Shared Driving Parameters

These flags are used by `demo`, `collect`, and `infer`.

| Flag | Type | Default | Simple meaning |
| --- | --- | --- | --- |
| `--backend` | `mock` or `carla` | `mock` | Which simulator to use. `mock` is the built-in simple simulator. `carla` is the real CARLA backend. |
| `--steps` | `int` | `120` | How many loop steps to run. |
| `--host` | `string` | `127.0.0.1` | CARLA server address when using `carla`. |
| `--port` | `int` | `2000` | CARLA server port when using `carla`. |
| `--tm-port` | `int` | `8000` | CARLA Traffic Manager port used when `autopilot` is active. |
| `--spawn-index` | `int` | `0` | Which CARLA spawn point to use. |
| `--vehicle-id` | `string` | `ego-001` | Vehicle name used in logs and telemetry. |
| `--camera-width` | `int` | `160` | Camera image width in pixels. |
| `--camera-height` | `int` | `90` | Camera image height in pixels. |
| `--spectator` | `none`, `chase`, or `hood` | `none` | Move CARLA's viewport with the ego vehicle. `hood` is POV-like, `chase` follows from behind. |
| `--target-speed` | `float` | `8.0` | Desired speed in meters per second. |
| `--publish-url` | `string` | `None` | Server URL for telemetry, such as `http://127.0.0.1:8765/telemetry`. |
| `--quiet` | flag | `False` | Show only the final summary instead of per-step output. |

## Command: `env`

### What it does

Prints environment details so you can confirm the project is set up correctly.

### Base command

```bash
py -3.12 main.py env
```

### Output to check

- Python version
- machine architecture
- NumPy version
- OpenCV version
- PyTorch version
- MPS availability
- CARLA API availability

## Command: `demo`

### What it does

Runs the driving loop without saving a dataset.

### Good time to use it

Use `demo` when you want to check that the simulator, controller, and loop all work.

### Base command

```bash
py -3.12 main.py demo [options]
```

### Extra parameters for `demo`

| Flag | Type | Default | Simple meaning |
| --- | --- | --- | --- |
| `--controller` | `demo`, `lane`, or `autopilot` | `demo` | Which controller should drive the car. |
| `--show-env` | flag | `False` | Print environment details before the run starts. |

### Controller choices

- `demo`: a simple scripted controller
- `lane`: a rule-based lane-keeping controller
- `autopilot`: CARLA Traffic Manager drives while the project records the applied controls

### Example commands

```bash
py -3.12 main.py demo --backend mock --steps 50
py -3.12 main.py demo --backend mock --controller lane --steps 100 --quiet
py -3.12 main.py demo --backend carla --host 127.0.0.1 --port 2000 --steps 100 --spawn-index 1 --spectator chase
```

### Output to check

- final JSON summary
- `distance_traveled_m`
- `collision_detected`

## Command: `collect`

### What it does

Runs the car and saves the drive to disk for training later.

### Good time to use it

Use `collect` before `train`.

### Base command

```bash
py -3.12 main.py collect [options]
```

### Extra parameters for `collect`

| Flag | Type | Default | Simple meaning |
| --- | --- | --- | --- |
| `--controller` | `demo`, `lane`, or `autopilot` | auto | Which controller collects the data. If omitted, the project chooses one automatically. |
| `--output` | `string/path` | auto | Where to save the recorded episode. If omitted, the project creates a timestamped folder in `data/episodes/`. |
| `--show-env` | flag | `False` | Print environment details before the run starts. |

### Output to check

- `metadata.json`
- `manifest.jsonl`
- `images/`

### Example commands

```bash
py -3.12 main.py collect --backend mock --steps 400
py -3.12 main.py collect --backend mock --controller lane --output data/episodes/mock_run_01
py -3.12 main.py collect --backend carla --controller autopilot --steps 1000 --output data/episodes/carla_run_01
```

## Command: `train`

### What it does

Trains the behavior-cloning model from a recorded dataset.

### Good time to use it

Use `train` after you have a dataset from `collect`.

### Base command

```bash
py -3.12 main.py train --dataset <episode_dir> [options]
```

### Parameters for `train`

| Flag | Type | Default | Required | Simple meaning |
| --- | --- | --- | --- | --- |
| `--dataset` | `one or more string/path values` | none | yes | One or more folders created by the `collect` command. |
| `--output` | `string/path` | `models/driving_model.pt` | no | Where to save the trained model. |
| `--epochs` | `int` | `5` | no | How many full training passes to run. |
| `--batch-size` | `int` | `16` | no | How many samples to train on at once. |
| `--learning-rate` | `float` | `0.001` | no | Training step size for the optimizer. |
| `--val-split` | `float` | `0.2` | no | Part of the dataset reserved for validation. |
| `--device` | `string` | `None` | no | Force a Torch device such as `cpu`, `mps`, or `cuda`. |
| `--num-workers` | `int` | `0` | no | Number of parallel workers used to load images during training. |
| `--log-interval` | `int` | `100` | no | Print training speed and loss every N batches. Use `0` to disable. |

### Training cheat sheet

| Setting | Plain-English meaning | Good beginner rule |
| --- | --- | --- |
| `--epochs` | How many times the model studies the full dataset. | Use `3` for a quick test and `8-10` for a more serious run. |
| `--batch-size` | How many images the model learns from before it updates itself. | Start with `16`. If memory is tight, use `8`. |
| `--num-workers` | How many helper processes load images while training is running. | Start with `4` or `6` on a stronger machine. |
| `--learning-rate` | How big each training update should be. | Keep the default `0.001` unless you have a clear reason to tune it. |
| `--device` | Which processor trains the model. | Use `cpu` for the safest setup, or `cuda` if PyTorch GPU support is working. |
| `--val-split` | How much data to hold back for a quick quality check. | Keep `0.2` unless your dataset is very small. |

### How the main training settings work together

- `1 epoch` means the model sees the whole dataset one time.
- `batch-size 16` means it learns from 16 images at a time during that pass.
- `num-workers 6` means 6 helpers load those images in parallel.

Example:

- `--epochs 5 --batch-size 16 --num-workers 6`
- This means: go through the whole dataset 5 times, train on 16 images at a time, and use 6 helpers to keep data loading moving.

Recommended starting points:

- quick test: `--epochs 3 --batch-size 16 --num-workers 4 --device cpu`
- larger run: `--epochs 8 --batch-size 16 --num-workers 6 --device cpu`
- GPU run: `--epochs 8 --batch-size 16 --num-workers 6 --device cuda`
- large CUDA TAR-index run: `--epochs 4 --batch-size 256 --num-workers 8 --device cuda --val-split 0.1`

### Example commands

```bash
py -3.12 main.py train --dataset data/episodes/mock_run_01
py -3.12 main.py train --dataset data/episodes/mock_run_01 --epochs 10 --batch-size 8
py -3.12 main.py train --dataset data/episodes/carla_run_01 data/episodes/carla_run_02 --output models/carla_combined.pt --num-workers 4
py -3.12 main.py train --dataset data/episodes/carla_run_01 --output models/carla_run_01_cuda.pt --device cuda
py -3.12 main.py train --dataset data/raw/carla_weekend_combined/carla_weekend_combined --output models/carla_weekend_tar_index_cuda.pt --device cuda --epochs 4 --batch-size 256 --num-workers 8 --val-split 0.1 --log-interval 100
```

### Output to check

- `train_loss`
- `val_loss`
- saved checkpoint path

## Command: `infer`

### What it does

Loads a trained model or uses CARLA autopilot as the active driving model.

### Good time to use it

Use `infer` after you have trained a model, or use `--autopilot-model` when you want CARLA's proven Traffic Manager behavior.

### Base command

```bash
py -3.12 main.py infer --checkpoint <model_path> [options]
py -3.12 main.py infer --backend carla --autopilot-model [options]
```

### Extra parameters for `infer`

| Flag | Type | Default | Required | Simple meaning |
| --- | --- | --- | --- | --- |
| `--checkpoint` | `string/path` | none | conditional | Path to the trained model file. Required unless `--autopilot-model` is used. |
| `--output` | `string/path` | `None` | no | If set, save the inference run as a new episode. |
| `--autopilot-guide` | flag | `False` | no | CARLA autopilot drives while the model still predicts controls for comparison. |
| `--autopilot-model` | flag | `False` | no | CARLA autopilot is the active driving model. No checkpoint is required. |
| `--show-env` | flag | `False` | no | Print environment details before the run starts. |

### Example commands

```bash
py -3.12 main.py infer --backend mock --checkpoint models/driving_model.pt
py -3.12 main.py infer --backend mock --checkpoint models/driving_model.pt --steps 200 --quiet
py -3.12 main.py infer --backend carla --autopilot-model --steps 3000 --spawn-index 1 --target-speed 8 --spectator chase
py -3.12 main.py infer --backend carla --checkpoint models/carla_weekend_tar_index_cuda.pt --publish-url http://127.0.0.1:8765/telemetry --spectator chase
py -3.12 main.py infer --backend carla --checkpoint models/carla_weekend_tar_index_cuda.pt --steps 300 --spawn-index 1 --target-speed 4 --spectator chase
py -3.12 main.py infer --backend carla --checkpoint models/carla_weekend_tar_index_cuda.pt --steps 3000 --spawn-index 1 --target-speed 8 --spectator hood
py -3.12 main.py infer --backend carla --checkpoint models/carla_weekend_tar_index_cuda.pt --steps 1000 --spawn-index 1 --target-speed 8 --spectator chase --autopilot-guide --output data/episodes/guided_spawn1_chase_01
```

The final inference summary includes run-quality metrics such as
`distance_traveled_m`, `average_speed_mps`, `max_speed_mps`,
`average_throttle`, and `average_brake`. In CARLA, collision reporting is
sticky for the full run: if the car hits something and later stops reporting a
live collision event, the final `collision_detected` value still stays `true`.
The summary can also include `first_collision_details`,
`last_collision_details`, `closest_obstacle_details`, and `blocked_detected`.
With `--autopilot-model`, CARLA Traffic Manager owns the driving controls.
With `--autopilot-guide`, the summary also includes
`average_abs_control_delta` and `max_abs_control_delta`, which show how far the
model's predictions were from CARLA autopilot's applied controls.

### Output to check

- `collision_detected`
- `carla_collision_detected`
- `blocked_detected`
- `closest_obstacle_details`
- `average_abs_control_delta` when using `--autopilot-guide`

## Command: `serve`

### What it does

Starts the central fleet coordination server.

### Good time to use it

Use `serve` when you want one or more vehicles to publish telemetry and receive alerts.

### Base command

```bash
py -3.12 main.py serve [options]
```

### Parameters for `serve`

| Flag | Type | Default | Simple meaning |
| --- | --- | --- | --- |
| `--host` | `string` | `127.0.0.1` | Network address the server should listen on. |
| `--port` | `int` | `8765` | Network port the server should listen on. |
| `--db` | `string/path` | `data/fleet/fleet.db` | SQLite database file used to store telemetry. |
| `--proximity-threshold` | `float` | `8.0` | Distance in meters that counts as a proximity warning. |
| `--stale-after` | `float` | `2.0` | Ignore telemetry older than this many seconds. |

### Example commands

```bash
py -3.12 main.py serve
py -3.12 main.py serve --host 0.0.0.0 --port 8765
py -3.12 main.py serve --db data/fleet/test.db --proximity-threshold 5.0 --stale-after 1.5
```

### Output to check

- server startup message
- telemetry responses from clients

## Common Workflows

### Workflow 1: Train and test a model

```bash
py -3.12 main.py env
py -3.12 main.py collect --backend mock --steps 400 --output data/episodes/run_01
py -3.12 main.py train --dataset data/episodes/run_01 --output models/driving_model.pt
py -3.12 main.py infer --backend mock --checkpoint models/driving_model.pt --steps 100
```

### Workflow 2: Evaluate a CARLA checkpoint

Use this after CARLA is open and a checkpoint has been trained.

```bash
py -3.12 main.py env
py -3.12 -c "import carla; c=carla.Client('127.0.0.1',2000); c.set_timeout(5.0); w=c.get_world(); print('frame:', w.get_snapshot().frame); print('map:', w.get_map().name)"
py -3.12 main.py demo --backend carla --steps 100 --spawn-index 1 --target-speed 8 --quiet
py -3.12 main.py infer --backend carla --autopilot-model --steps 3000 --spawn-index 1 --target-speed 8 --spectator chase
py -3.12 main.py infer --backend carla --checkpoint models/carla_weekend_tar_index_cuda.pt --steps 300 --spawn-index 1 --target-speed 4 --spectator chase
py -3.12 main.py infer --backend carla --checkpoint models/carla_weekend_tar_index_cuda.pt --steps 1000 --spawn-index 1 --target-speed 8 --spectator chase --autopilot-guide --output data/episodes/guided_spawn1_chase_01
```

A large TAR-indexed dataset can be trained from a dataset root such as:

```text
data/raw/carla_weekend_combined/carla_weekend_combined
```

When using a TAR-indexed dataset, keep the source TAR because the index points
into it and is not a copy of the images.

### Workflow 3: Run one ego vehicle with CARLA background traffic and pedestrians

Use this when you want your model or autopilot car to drive in a busier CARLA world without running multiple copies of `main.py`.

Terminal 1, from the CARLA installation folder:

```bash
py -3.12 PythonAPI/examples/generate_traffic.py --host 127.0.0.1 --port 2000 --tm-port 8000 --number-of-vehicles 30 --number-of-walkers 60 --safe
```

Terminal 2, from this project folder:

```bash
py -3.12 main.py infer --backend carla --autopilot-model --steps 5000 --spawn-index 1 --target-speed 8 --spectator chase
```

For a 30-sim-minute guided data collection run, use:

```bash
py -3.12 main.py infer --backend carla --checkpoint models/carla_weekend_tar_index_cuda.pt --steps 36000 --spawn-index 1 --target-speed 8 --spectator chase --autopilot-guide --output data/episodes/traffic_ped_guided_30min --quiet
```

Or run the Windows helper:

```bash
scripts\collect_traffic_pedestrians_30min_windows.bat
```

Important notes:

- both commands must point to the same CARLA host and port
- the traffic script adds the background vehicles and pedestrians
- `36000` steps is 30 simulated minutes at `fixed_delta_seconds=0.05`
- use one ego vehicle from this project at a time unless the runtime is upgraded for multi-ego support
- background traffic is safer than running several copies of `main.py` in the same world

### Workflow 4: Run the fleet server

Terminal 1:

```bash
py -3.12 main.py serve --host 0.0.0.0 --port 8765
```

Terminal 2:

```bash
py -3.12 main.py infer --backend carla --checkpoint models/carla_weekend_tar_index_cuda.pt --publish-url http://127.0.0.1:8765/telemetry --spectator chase --autopilot-guide
```

## Simple Glossary

- `backend`: the simulator implementation
- `checkpoint`: the saved trained model file
- `dataset`: the recorded training folder
- `episode`: one saved driving run
- `publish-url`: the server address used for telemetry
- `spawn-index`: the CARLA start location number
- `target-speed`: the speed the controller tries to maintain
- `telemetry`: shared vehicle data such as position, speed, and heading
