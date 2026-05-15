# File And Command Guide

This guide explains the project in the simplest useful way:

- which file you actually run,
- what each script does,
- how the pieces connect,
- and which commands matter most.

## The Most Important Rule

This project prefers `py -3.12` in command examples so the Python version is explicit and consistent.

- On Windows, use `py -3.12`
- On macOS or Linux, replace `py -3.12` with `python3`

You normally run one file:

```bash
py -3.12 main.py <command> [options]
```

Almost every other Python file supports `main.py`.

On Windows, `py.cmd` is included at the repo root. It lets `py -3.12 ...` use
the project `.venv` from Command Prompt even when the global Windows Python
Launcher is not installed.

## If You Only Remember Three Things

1. `main.py` is the control center.
2. `self_driving/` contains the real project code.
3. `docs/` contains the explanation and UML documents.

## Top-Level Files

| File | Simple purpose | Why it matters |
| --- | --- | --- |
| `main.py` | Main entrypoint for the whole project | This is the file you run |
| `README.md` | Main project overview | Best place to start reading |
| `py.cmd` | Windows command shim | Lets `py -3.12 ...` run the project venv from the repo folder |
| `pyproject.toml` | Project metadata and Python requirement | Helps keep the environment consistent |
| `.gitignore` | Tells Git which files not to track | Prevents local or generated files from being committed |

## Documentation Files

| File | Simple purpose |
| --- | --- |
| `docs/self_driving_uml_final.md` | Full UML and system specification |
| `docs/self_driving_use_case.md` | Shorter use-case summary |
| `docs/project_scope_proposal.md` | Research scope, proposal direction, and continuation plan |
| `docs/cli_command_reference.md` | Every command and parameter |
| `docs/file_and_command_guide.md` | This file |
| `docs/paper_outline.md` | Research paper outline in Markdown |
| `docs/paper_outline_google_docs.docx` | Paper outline in Word/Google Docs format |

## Data Folder

| Path | Simple purpose |
| --- | --- |
| `data/` | Stores generated outputs such as recorded episodes and fleet databases |

This folder is mostly project output, not source code.

Large CARLA datasets can also be stored as a dataset root such as:

```text
data\raw\carla_weekend_combined\carla_weekend_combined
```

When a dataset uses a TAR image index, it is backed by a source archive such as:

```text
C:\Carla Data\carla_weekend_combined.tar
```

The dataset uses `tar_image_index.jsonl` to read images directly from the TAR
instead of requiring a full extraction into millions of PNG files.

## Source Code Folder: `self_driving/`

This folder contains the real project logic.

## Files Most People Care About First

| File | Simple purpose | Extra detail for advanced use |
| --- | --- | --- |
| `self_driving/config.py` | Holds run settings | Creates the `SimulationConfig` object used across the project |
| `self_driving/control.py` | Built-in driving logic | Contains `DemoController` and `LaneKeepingController` |
| `self_driving/inference.py` | Lets the trained model drive | Contains `ModelController` |
| `self_driving/training.py` | Trains the AI model | Handles dataset loading, training, validation, and saving |
| `self_driving/pipeline.py` | Runs the main loop | Connects simulator, controller, recorder, and telemetry |

## Full File-By-File Explanation

### `self_driving/__init__.py`

Simple purpose:
- Marks `self_driving` as a Python package.

Why skilled users care:
- Mostly structural. It helps Python import the package cleanly.

### `self_driving/config.py`

Simple purpose:
- Stores the settings for a run.

What it controls:
- backend
- host
- port
- number of steps
- vehicle ID
- camera size

Why skilled users care:
- If you add new runtime settings, they usually belong here.

### `self_driving/types.py`

Simple purpose:
- Defines the shared data formats used across the project.

Main objects:
- `Pose2D`
- `ControlCommand`
- `VehicleState`
- `DrivingObservation`

Why skilled users care:
- These types define what data moves between the simulator, controller, recorder, and server.

### `self_driving/control.py`

Simple purpose:
- Contains built-in drivers.

Main parts:
- `Controller`: common interface
- `AutopilotController`: CARLA-native teacher driver for data collection
- `DemoController`: simple scripted driver
- `LaneKeepingController`: rule-based lane follower

Why skilled users care:
- This is where you change or replace the non-ML driving behavior.

### `self_driving/modeling.py`

Simple purpose:
- Defines the neural network and model helper functions.

Main parts:
- `DrivingModel`
- `image_to_tensor()`
- `select_torch_device()`
- `load_driving_model()`

Why skilled users care:
- This is where you change the model architecture or loading behavior.

### `self_driving/inference.py`

Simple purpose:
- Uses the trained model to make driving decisions.

Main part:
- `ModelController`

What it does:
- loads the model
- converts images into tensors
- predicts steering, throttle, and brake

Why skilled users care:
- This is the bridge between the trained model and the live control loop.

### `self_driving/training.py`

Simple purpose:
- Trains the model from recorded data.

Main parts:
- `TrainingConfig`
- `train_model()`
- `split_dataset()`
- `train_one_epoch()`
- `evaluate()`

Why skilled users care:
- This is where you tune training behavior, validation, and optimization.
- It now supports training from multiple episode folders and parallel data-loading workers.

### `self_driving/pipeline.py`

Simple purpose:
- Runs the main project loop.

What it does:
- starts the simulator
- gets observations
- asks the controller for a command
- steps the simulator
- records data if needed
- publishes telemetry if enabled

Main function:
- `run_loop()`

Why skilled users care:
- This is the core runtime path of the project.

### `self_driving/runner.py`

Simple purpose:
- A small wrapper around the main loop.

Why skilled users care:
- It is lightweight now, because `pipeline.py` handles most of the real work.

## Data Files

### `self_driving/data/__init__.py`

Simple purpose:
- Marks the data folder as a Python package.

### `self_driving/data/recording.py`

Simple purpose:
- Saves a driving run to disk.

Main part:
- `EpisodeRecorder`

What it writes:
- `metadata.json`
- `manifest.jsonl`
- frame images

Why skilled users care:
- This file defines how training data is stored.

### `self_driving/data/dataset.py`

Simple purpose:
- Loads saved data back into memory for training.

Main parts:
- `load_manifest_records()`
- `load_tar_image_index()`
- `DrivingDataset`

What it does:
- reads the manifest
- loads images from disk when present
- falls back to TAR-indexed image reads when needed
- converts them into tensors
- returns training targets

Why skilled users care:
- This file controls how recorded data becomes model input.
- TAR-indexed datasets depend on the index file and the original TAR file.

## Simulator Files

### `self_driving/simulator/__init__.py`

Simple purpose:
- Marks the simulator folder as a package.

### `self_driving/simulator/base.py`

Simple purpose:
- Defines the simulator interface used by the rest of the project.

Main part:
- `SimulatorClient`

Required methods:
- `setup()`
- `get_observation()`
- `step()`
- `teardown()`

Why skilled users care:
- New simulator backends should follow this interface.

### `self_driving/simulator/mock.py`

Simple purpose:
- Provides a built-in simple simulator.

What it does:
- simulates vehicle motion
- creates a fake front camera image
- creates lane offset and heading error

Main part:
- `MockSimulatorClient`

Why skilled users care:
- Useful for testing the software pipeline without needing full CARLA behavior.

### `self_driving/simulator/carla_adapter.py`

Simple purpose:
- Connects the project to the real CARLA simulator.

What it does:
- connects to the CARLA server
- spawns the vehicle
- attaches a camera
- attaches a collision sensor
- reads vehicle state and frames

Main part:
- `CarlaSimulatorClient`

Why skilled users care:
- This is the real simulator integration layer.

## Networking Files

### `self_driving/networking/__init__.py`

Simple purpose:
- Marks the networking folder as a package.

### `self_driving/networking/messages.py`

Simple purpose:
- Defines the message formats used in fleet communication.

Main parts:
- `FleetMessage`
- `CollisionAlert`

Why skilled users care:
- This file defines what data is shared across vehicles and the server.

### `self_driving/networking/client.py`

Simple purpose:
- Sends telemetry from a vehicle to the server.

Main part:
- `TelemetryPublisher`

What it does:
- sends HTTP POST requests to `/telemetry`
- receives advisory alerts back

Why skilled users care:
- This is the outgoing fleet communication path.

### `self_driving/networking/coordinator.py`

Simple purpose:
- Decides when vehicles may be in conflict.

Main part:
- `FleetCoordinator`

What it does:
- stores telemetry in SQLite
- checks nearby vehicles
- checks predicted path overlap
- creates advisory alerts

Why skilled users care:
- This file contains the main coordination logic for your research topic.

### `self_driving/networking/server.py`

Simple purpose:
- Runs the HTTP server for coordination.

What it provides:
- `GET /health`
- `GET /vehicles`
- `POST /telemetry`

Main function:
- `serve_coordinator()`

Why skilled users care:
- This is the service layer that exposes the coordinator to vehicles.

## What Happens When You Run Each Command

Each command explanation follows the same format:

- Purpose
- Base command
- What happens
- Main files involved

### Command: `env`

Purpose:
- check whether the local environment can run the project

Base command:

```bash
py -3.12 main.py env
```

What happens:
- the project prints Python and package information

Main files involved:
- `main.py`

### Command: `demo`

Purpose:
- run a simulator loop without saving a dataset

Base command:

```bash
py -3.12 main.py demo [options]
```

What happens:
- the project starts a simulator
- chooses a built-in controller
- runs the driving loop

Main files involved:
- `main.py`
- `self_driving/control.py`
- `self_driving/pipeline.py`
- `self_driving/simulator/mock.py` or `self_driving/simulator/carla_adapter.py`

### Command: `collect`

Purpose:
- save a driving episode for later training

Base command:

```bash
py -3.12 main.py collect [options]
```

What happens:
- the project runs the car
- saves images and metadata
- on CARLA, it can use native autopilot so the saved labels follow the road better

Main files involved:
- `main.py`
- `self_driving/control.py`
- `self_driving/pipeline.py`
- `self_driving/data/recording.py`
- simulator backend

### Command: `train`

Purpose:
- train a checkpoint from one or more recorded datasets

Base command:

```bash
py -3.12 main.py train --dataset <episode_dir> [options]
```

What happens:
- the project loads a recorded dataset
- trains a model
- saves a checkpoint
- it can combine multiple recorded runs into one training job
- saves epoch checkpoints during longer runs
- prints training speed and loss when `--log-interval` is enabled

Main files involved:
- `main.py`
- `self_driving/data/dataset.py`
- `self_driving/modeling.py`
- `self_driving/training.py`

### Command: `infer`

Purpose:
- run a saved checkpoint or CARLA autopilot in the driving loop

Base command:

```bash
py -3.12 main.py infer --checkpoint <model_path> [options]
py -3.12 main.py infer --backend carla --autopilot-model [options]
```

What happens:
- the project loads a checkpoint, unless `--autopilot-model` is used
- the checkpoint model or CARLA autopilot drives the vehicle
- the loop can optionally record or publish telemetry
- CARLA runs can move the spectator camera with the ego car using `--spectator hood` or `--spectator chase`
- CARLA autopilot can be used directly as the active model with `--autopilot-model`
- CARLA autopilot can be used as a guide with `--autopilot-guide`, where autopilot drives and the model is compared against it
- the final summary includes distance, speed, throttle, brake, collision, and obstacle metrics

Main files involved:
- `main.py`
- `self_driving/modeling.py`
- `self_driving/inference.py`
- `self_driving/pipeline.py`
- simulator backend

### Command: `serve`

Purpose:
- start the fleet telemetry and collision-advisory server

Base command:

```bash
py -3.12 main.py serve [options]
```

What happens:
- the project starts the fleet coordination server
- incoming telemetry is stored and checked for alerts

Main files involved:
- `main.py`
- `self_driving/networking/server.py`
- `self_driving/networking/coordinator.py`
- `self_driving/networking/messages.py`

## Which Files You Usually Do Not Run Directly

You usually do not run these files directly:

- anything inside `self_driving/`
- any `__init__.py` file
- `self_driving/pipeline.py`
- `self_driving/training.py`
- `self_driving/inference.py`
- simulator files
- networking files

They are project modules, not normal entrypoints.

## Most Important Commands

Each command block below uses the same format:

- Purpose
- Example commands
- Output to check

### Check the environment

Purpose:
- verify Python, packages, PyTorch, and CARLA API

```bash
py -3.12 main.py env
```

Output to check:
- `PyTorch`
- `CARLA API`

### Run a simple demo

Purpose:
- run a quick loop without writing a dataset

```bash
py -3.12 main.py demo --backend mock --controller lane --steps 100
py -3.12 main.py demo --backend carla --steps 100 --spawn-index 1 --target-speed 8 --spectator chase
```

Output to check:
- `distance_traveled_m`
- `collision_detected`

### Record a dataset

Purpose:
- create training data from mock control or CARLA autopilot

```bash
py -3.12 main.py collect --backend mock --steps 400 --output data/episodes/run_01
py -3.12 main.py collect --backend carla --controller autopilot --steps 1000 --output data/episodes/carla_run_01 --spectator chase
```

Output to check:
- `metadata.json`
- `manifest.jsonl`
- `images/`

### Train the model

Purpose:
- train a checkpoint from recorded data

```bash
py -3.12 main.py train --dataset data/episodes/run_01 --output models/driving_model.pt
py -3.12 main.py train --dataset data/episodes/run_01 data/episodes/run_02 --output models/driving_model.pt --num-workers 4
py -3.12 main.py train --dataset data/episodes/carla_fleet_overnight_01/vehicle_01 data/episodes/carla_fleet_overnight_01/vehicle_02 data/episodes/carla_fleet_overnight_01/vehicle_03 --output models/carla_fleet_teacher_cuda.pt --device cuda --epochs 4 --batch-size 128 --num-workers 8 --val-split 0.1 --log-interval 100
py -3.12 main.py train --dataset data/raw/carla_weekend_combined/carla_weekend_combined --output models/carla_weekend_tar_index_cuda.pt --device cuda --epochs 4 --batch-size 256 --num-workers 8 --val-split 0.1 --log-interval 100
py -3.12 main.py train --init-checkpoint models/carla_lane_recovery_cuda.pt --dataset data/episodes/traffic_ped_guided_1h_01 data/episodes/lane_correction_spawn1_speed4_01 data/episodes/recovery_spawn1_right_yaw_01 data/episodes/recovery_spawn1_left_yaw_01 data/episodes/recovery_spawn1_right_counter_01 data/episodes/recovery_spawn1_left_counter_01 data/episodes/autopilot_teacher_spawn1_30min_01 --output models/carla_teacher_refined_cuda.pt --device cuda --epochs 4 --batch-size 128 --num-workers 8 --learning-rate 0.00005 --val-split 0.1 --log-interval 100
```

Output to check:
- `train_loss`
- `val_loss`
- saved checkpoint path

### Run the trained model

Purpose:
- evaluate a checkpoint in mock mode or CARLA

```bash
py -3.12 main.py infer --backend mock --checkpoint models/driving_model.pt --steps 100
py -3.12 main.py infer --backend carla --autopilot-model --steps 3000 --spawn-index 1 --target-speed 8 --spectator chase
py -3.12 main.py infer --backend carla --checkpoint models/carla_weekend_tar_index_cuda.pt --steps 300 --spawn-index 1 --target-speed 4 --spectator chase
py -3.12 main.py infer --backend carla --checkpoint models/carla_teacher_refined_cuda.pt --steps 600 --spawn-index 1 --target-speed 4 --spectator chase --lane-guard --traffic-rule-guard
py -3.12 main.py infer --backend carla --checkpoint models/carla_weekend_tar_index_cuda.pt --steps 3000 --spawn-index 1 --target-speed 8 --spectator hood
py -3.12 main.py infer --backend carla --checkpoint models/carla_weekend_tar_index_cuda.pt --steps 1000 --spawn-index 1 --target-speed 8 --spectator chase --autopilot-guide --output data/episodes/guided_spawn1_chase_01
py -3.12 main.py infer --backend carla --checkpoint models/carla_teacher_refined_cuda.pt --steps 600 --spawn-index 1 --target-speed 4 --spectator chase --autopilot-guide --output data/episodes/test_refined_model_01
py -3.12 main.py infer --backend carla --checkpoint models/carla_weekend_tar_index_cuda.pt --steps 36000 --spawn-index 1 --target-speed 8 --spectator chase --autopilot-guide --output data/episodes/traffic_ped_guided_30min --quiet
```

Output to check:
- `collision_detected`
- `carla_collision_detected`
- `blocked_detected`
- `closest_obstacle_details`
- `average_abs_control_delta` when using `--autopilot-guide`

### Start the fleet server

Purpose:
- run the telemetry coordination server

```bash
py -3.12 main.py serve --host 0.0.0.0 --port 8765
```

Output to check:
- server startup message
- telemetry responses from clients

## Practical Training Process Used In This Project

This project used an iterative training process instead of relying on one dataset and one model.

### Multi-car overnight collection

For larger teacher datasets, use `collect-fleet` instead of opening several
`collect` terminals. It spawns multiple CARLA autopilot vehicles in one
synchronized world and writes one episode folder per vehicle:

```bash
py -3.12 main.py collect-fleet --backend carla --vehicles 3 --spawn-indices 1 8 15 --steps 360000 --output-root data/episodes/carla_fleet_overnight_01 --checkpoint models/carla_teacher_refined_cuda.pt --target-speed 8 --lane-guard --traffic-rule-guard --quiet
scripts\collect_fleet_overnight_windows.bat
```

With `--checkpoint`, CARLA autopilot still drives each recorded car. The current
model predicts in the background, and those predictions are written as
`requested_control` so the run captures where the model disagrees with the
teacher.

To run several improvement rounds automatically:

```bash
scripts\iterate_fleet_model_windows.bat
```

Each round collects three guided fleet episode folders and trains the next
checkpoint from them. This is the safer way to iterate because the labels still
come from CARLA autopilot rather than from the current model's own mistakes.

For a quick 10-car comparison and short fine-tune:

```bash
scripts\quick_iterate_10car_5min_windows.bat
```

This runs 10 guided CARLA autopilot cars for 5 simulated minutes. After
collection, inspect `fleet_summary.json` under the generated output folder to
compare the current model's predicted controls against CARLA autopilot.

The resulting folders can be trained together:

```bash
py -3.12 main.py train --dataset data/episodes/carla_fleet_overnight_01/vehicle_01 data/episodes/carla_fleet_overnight_01/vehicle_02 data/episodes/carla_fleet_overnight_01/vehicle_03 --output models/carla_fleet_teacher_cuda.pt --device cuda --epochs 4 --batch-size 128 --num-workers 8 --val-split 0.1 --log-interval 100
```

### What was done

1. Several short CARLA autopilot collection runs were recorded.
2. Those runs were trained together as one combined dataset.
3. The combined model was tested in CARLA with `infer`.
4. The results were observed and used to decide whether more data was needed.
5. After several short-run iterations, a much longer CARLA autopilot run was started to build a stronger dataset.

### The short-run collection pattern

The early CARLA runs were recorded as separate episode folders such as:

- `data/episodes/carla_auto_01`
- `data/episodes/carla_auto_02`
- `data/episodes/carla_auto_03`
- `data/episodes/carla_auto_04`
- `data/episodes/carla_auto_05`

Saving them separately mattered because it made it easier to:

- keep each test organized
- combine multiple runs into one model later
- stop and restart the process without losing older datasets

### The combined training pattern

Those five runs were then trained together:

```bash
py -3.12 main.py train --dataset data/episodes/carla_auto_01 data/episodes/carla_auto_02 data/episodes/carla_auto_03 data/episodes/carla_auto_04 data/episodes/carla_auto_05 --output models/carla_auto_combined_v2.pt --epochs 8 --batch-size 16 --num-workers 6
```

Simple meaning:

- one model
- trained from five recorded runs
- repeated for 8 epochs
- using 16 images at a time
- with 6 helper workers loading data

### The validation pattern

After training, the model was tested in CARLA:

```bash
py -3.12 main.py infer --backend carla --checkpoint models/carla_auto_combined_v2.pt --steps 200 --spawn-index 1 --spectator chase
```

This was not just for show. It answered an important question:

- is the model actually producing live control outputs that move the vehicle?

Even when the model was imperfect, this test helped separate:

- pipeline problems
- from weak learned driving behavior

### What was learned from the early tests

The first learned models were active, but not stable enough yet. Observed behaviors included:

- moving only a short distance before stopping
- driving into a curb or building
- producing nonzero throttle while still making poor road decisions

This was treated as a sign that:

- the software pipeline was working
- but the model still needed more and better data

### Why the long collection run came next

After several short-run iterations, the next step was to start a long CARLA autopilot collection run so the model could learn from a much larger and more realistic dataset.

The long-run command used was:

```bash
py -3.12 main.py collect --backend carla --controller autopilot --steps 700000 --output data/episodes/carla_overnight_01 --quiet
```

Why this was useful:

- the CARLA autopilot acts as the teacher driver
- the long run captures more turns, lane following, and traffic behavior
- `quiet` keeps the terminal output small during unattended runs

### Best way to describe this project process

In one sentence:

- several short CARLA training runs were collected and combined into one model, that model was tested and retrained iteratively, and once the workflow was stable, a long CARLA autopilot run was started to build a stronger dataset for the next training cycle.

## Large CARLA Dataset Workflow

For large CARLA datasets, keep the project flow the same: train a checkpoint,
then evaluate it in CARLA. TAR-indexed datasets let the loader read images from
the source archive without extracting millions of files.

Useful health and evaluation commands:

```bash
py -3.12 main.py env
py -3.12 -c "import carla; c=carla.Client('127.0.0.1',2000); c.set_timeout(5.0); w=c.get_world(); print('frame:', w.get_snapshot().frame); print('map:', w.get_map().name)"
py -3.12 main.py demo --backend carla --steps 100 --spawn-index 1 --target-speed 8 --quiet
py -3.12 main.py infer --backend carla --autopilot-model --steps 3000 --spawn-index 1 --target-speed 8 --spectator chase
py -3.12 main.py infer --backend carla --checkpoint models/carla_weekend_tar_index_cuda.pt --steps 300 --spawn-index 1 --target-speed 4 --spectator chase
py -3.12 main.py infer --backend carla --checkpoint models/carla_teacher_refined_cuda.pt --steps 600 --spawn-index 1 --target-speed 4 --spectator chase --lane-guard --traffic-rule-guard
py -3.12 main.py infer --backend carla --checkpoint models/carla_weekend_tar_index_cuda.pt --steps 1000 --spawn-index 1 --target-speed 8 --spectator chase --autopilot-guide --output data/episodes/guided_spawn1_chase_01
```

For a 30-sim-minute traffic and pedestrian collection run, start CARLA's traffic
script in one terminal and then run:

```bash
scripts\collect_traffic_pedestrians_30min_windows.bat
```

If CARLA's `generate_traffic.py` says `ModuleNotFoundError: No module named
'carla'`, install the CARLA Python API once from the CARLA folder:

```bash
py -3.12 -m pip install PythonAPI/carla/dist/carla-0.9.16-cp312-cp312-win_amd64.whl
```

## Best Mental Model

- `main.py` = the control center
- `simulator/` = where the world comes from
- `control.py` and `inference.py` = where driving decisions come from
- `data/` and `training.py` = where learning comes from
- `networking/` = where vehicles share information
- `docs/` = where your explanations and UML live
