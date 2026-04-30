# File And Command Guide

This guide explains the project in the simplest useful way:

- which file you actually run,
- what each script does,
- how the pieces connect,
- and which commands matter most.

## The Most Important Rule

You normally run one file:

```bash
python3 main.py <command> [options]
```

Almost every other Python file supports `main.py`.

## If You Only Remember Three Things

1. `main.py` is the control center.
2. `self_driving/` contains the real project code.
3. `docs/` contains the explanation and UML documents.

## Top-Level Files

| File | Simple purpose | Why it matters |
| --- | --- | --- |
| `main.py` | Main entrypoint for the whole project | This is the file you run |
| `README.md` | Main project overview | Best place to start reading |
| `pyproject.toml` | Project metadata and Python requirement | Helps keep the environment consistent |
| `.gitignore` | Tells Git which files not to track | Prevents local or generated files from being committed |

## Documentation Files

| File | Simple purpose |
| --- | --- |
| `docs/self_driving_uml_final.md` | Full UML and system specification |
| `docs/self_driving_use_case.md` | Shorter use-case summary |
| `docs/cli_command_reference.md` | Every command and parameter |
| `docs/file_and_command_guide.md` | This file |
| `docs/paper_outline.md` | Research paper outline in Markdown |
| `docs/paper_outline_google_docs.docx` | Paper outline in Word/Google Docs format |

## Data Folder

| Path | Simple purpose |
| --- | --- |
| `data/` | Stores generated outputs such as recorded episodes and fleet databases |

This folder is mostly project output, not source code.

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
- `DrivingDataset`

What it does:
- reads the manifest
- loads images
- converts them into tensors
- returns training targets

Why skilled users care:
- This file controls how recorded data becomes model input.

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

### `python3 main.py env`

What happens:
- the project prints Python and package information

Main files involved:
- `main.py`

### `python3 main.py demo`

What happens:
- the project starts a simulator
- chooses a built-in controller
- runs the driving loop

Main files involved:
- `main.py`
- `self_driving/control.py`
- `self_driving/pipeline.py`
- `self_driving/simulator/mock.py` or `self_driving/simulator/carla_adapter.py`

### `python3 main.py collect`

What happens:
- the project runs the car
- saves images and metadata

Main files involved:
- `main.py`
- `self_driving/control.py`
- `self_driving/pipeline.py`
- `self_driving/data/recording.py`
- simulator backend

### `python3 main.py train`

What happens:
- the project loads a recorded dataset
- trains a model
- saves a checkpoint

Main files involved:
- `main.py`
- `self_driving/data/dataset.py`
- `self_driving/modeling.py`
- `self_driving/training.py`

### `python3 main.py infer`

What happens:
- the project loads a checkpoint
- the model drives the vehicle
- the loop can optionally record or publish telemetry

Main files involved:
- `main.py`
- `self_driving/modeling.py`
- `self_driving/inference.py`
- `self_driving/pipeline.py`
- simulator backend

### `python3 main.py serve`

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

### Check the environment

```bash
python3 main.py env
```

### Run a simple demo

```bash
python3 main.py demo --backend mock --controller lane --steps 100
```

### Record a dataset

```bash
python3 main.py collect --backend mock --steps 400 --output data/episodes/run_01
```

### Train the model

```bash
python3 main.py train --dataset data/episodes/run_01 --output models/driving_model.pt
```

### Run the trained model

```bash
python3 main.py infer --backend mock --checkpoint models/driving_model.pt --steps 100
```

### Start the fleet server

```bash
python3 main.py serve --host 0.0.0.0 --port 8765
```

## Best Mental Model

- `main.py` = the control center
- `simulator/` = where the world comes from
- `control.py` and `inference.py` = where driving decisions come from
- `data/` and `training.py` = where learning comes from
- `networking/` = where vehicles share information
- `docs/` = where your explanations and UML live
