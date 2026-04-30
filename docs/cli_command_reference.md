# CLI Command Reference

This file explains every command in the project in plain language while still keeping the full parameter list.

## The Main Rule

You normally run the project through one file:

```bash
python3 main.py <command> [options]
```

## What Each Command Means

| Command | Simple meaning | When to use it |
| --- | --- | --- |
| `env` | Check your Python environment | Use first, before running anything else |
| `demo` | Drive without saving data | Use for quick testing |
| `collect` | Save a driving dataset | Use before training |
| `train` | Train the driving model | Use after collecting data |
| `infer` | Let the trained model drive | Use to test the model |
| `serve` | Start the fleet server | Use when vehicles should publish telemetry |

## Important Command Behavior

- If you run `python3 main.py` with no command, the project starts `demo`.
- If you run `python3 main.py --some-flag`, the project also treats that as `demo`.
- That means `python3 main.py --help` behaves like `demo --help`.

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
| `--target-speed` | `float` | `8.0` | Desired speed in meters per second. |
| `--publish-url` | `string` | `None` | Server URL for telemetry, such as `http://127.0.0.1:8765/telemetry`. |
| `--quiet` | flag | `False` | Show only the final summary instead of per-step output. |

## Command: `env`

### What it does

Prints environment details so you can confirm the project is set up correctly.

### Command

```bash
python3 main.py env
```

### What it prints

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

### Command

```bash
python3 main.py demo [options]
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
python3 main.py demo --backend mock --steps 50
python3 main.py demo --backend mock --controller lane --steps 100 --quiet
python3 main.py demo --backend carla --host 127.0.0.1 --port 2000 --steps 100
```

## Command: `collect`

### What it does

Runs the car and saves the drive to disk for training later.

### Good time to use it

Use `collect` before `train`.

### Command

```bash
python3 main.py collect [options]
```

### Extra parameters for `collect`

| Flag | Type | Default | Simple meaning |
| --- | --- | --- | --- |
| `--controller` | `demo`, `lane`, or `autopilot` | auto | Which controller collects the data. If omitted, the project chooses one automatically. |
| `--output` | `string/path` | auto | Where to save the recorded episode. If omitted, the project creates a timestamped folder in `data/episodes/`. |
| `--show-env` | flag | `False` | Print environment details before the run starts. |

### Files it creates

- `metadata.json`
- `manifest.jsonl`
- `images/`

### Example commands

```bash
python3 main.py collect --backend mock --steps 400
python3 main.py collect --backend mock --controller lane --output data/episodes/mock_run_01
python3 main.py collect --backend carla --controller autopilot --steps 1000 --output data/episodes/carla_run_01
```

## Command: `train`

### What it does

Trains the behavior-cloning model from a recorded dataset.

### Good time to use it

Use `train` after you have a dataset from `collect`.

### Command

```bash
python3 main.py train --dataset <episode_dir> [options]
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

### Example commands

```bash
python3 main.py train --dataset data/episodes/mock_run_01
python3 main.py train --dataset data/episodes/mock_run_01 --epochs 10 --batch-size 8
python3 main.py train --dataset data/episodes/carla_run_01 data/episodes/carla_run_02 --output models/carla_combined.pt --num-workers 4
python3 main.py train --dataset data/episodes/carla_run_01 --output models/carla_model.pt --device cuda
```

## Command: `infer`

### What it does

Loads a trained model and lets it drive the vehicle.

### Good time to use it

Use `infer` after you have trained a model.

### Command

```bash
python3 main.py infer --checkpoint <model_path> [options]
```

### Extra parameters for `infer`

| Flag | Type | Default | Required | Simple meaning |
| --- | --- | --- | --- | --- |
| `--checkpoint` | `string/path` | none | yes | Path to the trained model file. |
| `--output` | `string/path` | `None` | no | If set, save the inference run as a new episode. |
| `--show-env` | flag | `False` | no | Print environment details before the run starts. |

### Example commands

```bash
python3 main.py infer --backend mock --checkpoint models/driving_model.pt
python3 main.py infer --backend mock --checkpoint models/driving_model.pt --steps 200 --quiet
python3 main.py infer --backend carla --checkpoint models/carla_model.pt --publish-url http://127.0.0.1:8765/telemetry
```

## Command: `serve`

### What it does

Starts the central fleet coordination server.

### Good time to use it

Use `serve` when you want one or more vehicles to publish telemetry and receive alerts.

### Command

```bash
python3 main.py serve [options]
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
python3 main.py serve
python3 main.py serve --host 0.0.0.0 --port 8765
python3 main.py serve --db data/fleet/test.db --proximity-threshold 5.0 --stale-after 1.5
```

## Two Common Workflows

### Workflow 1: Train and test a model

```bash
python3 main.py env
python3 main.py collect --backend mock --steps 400 --output data/episodes/run_01
python3 main.py train --dataset data/episodes/run_01 --output models/driving_model.pt
python3 main.py infer --backend mock --checkpoint models/driving_model.pt --steps 100
```

### Workflow 2: Run the fleet server

Terminal 1:

```bash
python3 main.py serve --host 0.0.0.0 --port 8765
```

Terminal 2:

```bash
python3 main.py infer --backend carla --checkpoint models/carla_model.pt --publish-url http://127.0.0.1:8765/telemetry
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
