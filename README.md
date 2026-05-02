# Carla Self-Driving Car Seminar Project

## What This Project Is

This project builds a simple self-driving car workflow in the CARLA simulator.

In plain English, the project does five things:

1. It drives a car in simulation.
2. It saves what the car sees and how it drives.
3. It trains a model to copy that driving behavior.
4. It runs the trained model back in the simulator.
5. It shares vehicle data with a central service to look for possible collisions.

This makes the project useful for both:

- learning how a self-driving pipeline works,
- and studying how multiple vehicles might cooperate through shared telemetry.

## What The System Actually Does

The full workflow is:

1. Start a simulator.
2. Run a vehicle with a built-in controller.
3. Save camera frames, vehicle state, and control commands.
4. Train a behavior-cloning model from that dataset.
5. Run the trained model in a closed driving loop.
6. Optionally send vehicle telemetry to a fleet coordinator.
7. Generate collision advisories based on nearby vehicles and predicted path overlap.

## Why This Project Matters

A single self-driving vehicle can only react to what it can sense locally. That works, but it can be limited when traffic is dense, vehicles are close together, or one vehicle blocks another from view.

This project adds a second idea on top of the normal self-driving loop: vehicles can share telemetry with a central coordination service. That service can check where vehicles are, where they are heading, and whether their paths may conflict.

That is why the project is a good fit for research on cooperative collision awareness.

## Current Scope And Planned Continuation

This repository is part of a Seminar research project at William Paterson University. The current team is:

- Dylan Weaver
- Michael

The current repository scope is focused on the software side of the project:

- CARLA-based simulation
- data collection
- behavior-cloning model training
- model inference in simulation
- telemetry sharing and central coordination experiments

This project is also intended to continue beyond the current Seminar course. The longer-term research direction is to extend the work into graduate-level research and a broader sim-to-real autonomous vehicle platform.

Planned future phases include:

- small-scale RC vehicle testing
- guardian crash-avoidance overrides during manual driving
- sensor fusion and perception upgrades
- reinforcement learning experiments
- multi-vehicle mesh coordination for collision avoidance

The full proposal and scope document is here:

- [docs/project_scope_proposal.md](docs/project_scope_proposal.md)

## Main Parts Of The System

### 1. Simulation

The project supports two simulator backends:

- `mock`: a small built-in simulator used for fast testing
- `carla`: the real CARLA simulator backend

### 2. Data Collection

The system can record:

- front camera images
- vehicle state
- steering, throttle, and brake commands

This recorded data becomes the training dataset.

### 3. Model Training

The training pipeline learns a behavior-cloning model. That means the model tries to imitate how the controller drove during data collection.

### 4. Autonomous Inference

After training, the model can drive the vehicle in the simulator by predicting:

- steering
- throttle
- brake

### 5. Fleet Coordination

The project can also send telemetry to a central server. That server stores the data in SQLite and returns alerts when vehicles are too close or their predicted paths overlap.

## Quick Start

### Command convention

This project prefers `py -3.12` in command examples so the Python version is explicit and consistent.

- On Windows, use `py -3.12`
- On macOS or Linux, replace `py -3.12` with `python3`

### 1. Create a Python environment

```bash
py -3.12 -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

```bash
py -3.12 -m pip install numpy opencv-python torch
```

If you want to use the real CARLA backend, install the CARLA Python API in the same environment.

### 3. Check the environment

```bash
py -3.12 main.py env
```

This prints:

- Python version
- machine architecture
- NumPy version
- OpenCV version
- PyTorch version
- MPS availability
- CARLA API availability

## Step-By-Step Usage

### Step 1. Run a simple driving loop

```bash
py -3.12 main.py demo --backend mock --steps 50
```

Use this when you just want to see the pipeline run without saving data.

### Step 2. Record a dataset

```bash
py -3.12 main.py collect --backend mock --steps 400 --output data/episodes/run_01
```

This creates a dataset folder that contains:

- `metadata.json`
- `manifest.jsonl`
- `images/`

On CARLA, `collect` now defaults to the built-in autopilot teacher so the saved controls are better than the simple demo driver.

### Step 3. Train the model

```bash
py -3.12 main.py train --dataset data/episodes/run_01 --output models/driving_model.pt
```

This trains the model and saves it as `models/driving_model.pt`.

You can also train from multiple recorded runs at once:

```bash
py -3.12 main.py train --dataset data/episodes/run_01 data/episodes/run_02 --output models/driving_model.pt --num-workers 4
```

### Training settings in plain English

- `--epochs`: how many times the model goes through the full dataset
- `--batch-size`: how many images the model learns from at one time before it updates itself
- `--num-workers`: how many helper processes load images in parallel during training
- `--learning-rate`: how aggressively the optimizer changes the model each update
- `--device`: where training runs, usually `cpu` or `cuda`

Simple example:

- `--epochs 5 --batch-size 16 --num-workers 6`
- This means: go through the full dataset 5 times, learn from 16 images at a time, and use 6 helpers to keep data loading moving.

Good starting values:

- quick test: `--epochs 3 --batch-size 16 --num-workers 4`
- stronger run: `--epochs 8 --batch-size 16 --num-workers 6`
- if memory is tight: lower `--batch-size` from `16` to `8`

### Step 4. Run the trained model

```bash
py -3.12 main.py infer --backend mock --checkpoint models/driving_model.pt --steps 100
```

This loads the saved model and lets it drive the vehicle.

### Step 5. Start the fleet coordinator

```bash
py -3.12 main.py serve --host 0.0.0.0 --port 8765
```

This starts the central telemetry service.

### Step 6. Drive while publishing telemetry

```bash
py -3.12 main.py infer --backend mock --checkpoint models/driving_model.pt --publish-url http://127.0.0.1:8765/telemetry
```

This runs the car and sends its telemetry to the fleet server.

## Real Project Workflow Used In This Seminar

This project was not built from one dataset and one training run. The practical workflow was iterative:

1. Record a few short CARLA autopilot runs.
2. Train a model from those runs.
3. Test the model in CARLA with `infer`.
4. Observe what failed, such as stopping too early or steering into objects.
5. Collect more data and retrain a new combined model.
6. Repeat until the model behavior was stable enough to justify a long collection run.

In practice, the first serious CARLA collection runs were saved as:

- `data/episodes/carla_auto_01`
- `data/episodes/carla_auto_02`
- `data/episodes/carla_auto_03`
- `data/episodes/carla_auto_04`
- `data/episodes/carla_auto_05`

Those runs were then combined into one training job:

```bash
py -3.12 main.py train --dataset data/episodes/carla_auto_01 data/episodes/carla_auto_02 data/episodes/carla_auto_03 data/episodes/carla_auto_04 data/episodes/carla_auto_05 --output models/carla_auto_combined_v2.pt --epochs 8 --batch-size 16 --num-workers 6
```

The model was then tested in CARLA:

```bash
py -3.12 main.py infer --backend carla --checkpoint models/carla_auto_combined_v2.pt --steps 200 --spawn-index 1
```

That testing step was important because it showed whether the model was actually alive and making decisions, even if the driving was still unstable.

### Why the process was repeated

The first learned models proved that the pipeline worked, but they were not stable enough yet. Some early behaviors included:

- driving only a short distance and then stopping
- turning into a curb or building
- producing valid throttle and steering values, but still making weak decisions

That was treated as a data-quality and dataset-size problem, not as proof that the system was broken.

### Why a 12-hour collection run was used

After several short runs and retraining cycles, the next step was to collect a much larger CARLA autopilot dataset. The idea was:

- short runs prove the pipeline works
- repeated training stabilizes the workflow
- a long run gives the model much more realistic driving behavior to learn from

The long collection command used the CARLA autopilot teacher and `quiet` mode so it could run unattended:

```bash
py -3.12 main.py collect --backend carla --controller autopilot --steps 700000 --output data/episodes/carla_overnight_01 --quiet
```

This long run was intended to collect many more examples of:

- lane following
- turns
- traffic light stops
- general road behavior

The overall strategy was simple:

- use several smaller runs to validate and improve the model
- then use one long run to create a stronger training dataset
- then retrain from that larger dataset

## The Commands You Should Know

- `env`: check Python and package setup
- `demo`: run the system without saving a dataset
- `collect`: save a driving dataset
- `train`: train the driving model
- `infer`: run the trained model
- `serve`: start the fleet coordination server

The full parameter list is in [docs/cli_command_reference.md](docs/cli_command_reference.md).

## Overnight Helpers

For Windows overnight runs, use:

- `scripts/collect_overnight_windows.bat`: collects many smaller CARLA autopilot segments back-to-back
- `scripts/train_overnight_segments_windows.bat`: trains one model from all collected `segment_*` folders

The collection script is safer for long runs because completed segments remain usable even if the machine stops during the night.

## Using CARLA Traffic With This Project

The safest way to add more realistic road behavior is:

- run one ego vehicle from this project
- run background traffic from CARLA's default traffic script
- keep both pointed at the same CARLA host and port

Typical pattern:

### Terminal 1: CARLA traffic script

Run this from the CARLA installation folder if `generate_traffic.py` is available there:

```bash
py -3.12 PythonAPI/examples/generate_traffic.py --host 127.0.0.1 --port 2000 --number-of-vehicles 30
```

### Terminal 2: this project

Run your collection or inference command from this project folder:

```bash
py -3.12 main.py infer --backend carla --checkpoint models/carla_auto_combined_v2.pt --steps 5000 --spawn-index 1
```

Important rule:

- use one ego vehicle from this project at a time unless the code is explicitly upgraded for multi-ego synchronization

## UML Summary In Simple Terms

The formal UML package is in:

- [docs/self_driving_uml_final.md](docs/self_driving_uml_final.md)
- [docs/self_driving_use_case.md](docs/self_driving_use_case.md)
- [docs/project_scope_proposal.md](docs/project_scope_proposal.md)

The most important parts are:

### Main Actors

- `Project Developer / Researcher`
- `Simulation Runtime`
- `Central Fleet Database`
- `Other Fleet Vehicles`

### Main Use Cases

- `Configure / Start Simulation`
- `Collect Sensor Dataset`
- `Train Driving Model`
- `Run Autonomous Drive`
- `Publish Vehicle Telemetry`
- `Receive Collision Advisory`
- `Store Episode Logs and Metrics`

### Core Components

- `SimulationConfig`: stores run settings
- `SimulatorClient`: common simulator interface
- `MockSimulatorClient`: built-in test simulator
- `CarlaSimulatorClient`: real CARLA simulator adapter
- `AutopilotController`: records data from CARLA's native teacher driver
- `LaneKeepingController`: rule-based driver
- `ModelController`: trained-model driver
- `EpisodeRecorder`: saves dataset runs
- `DrivingDataset`: loads training data
- `DrivingModel`: neural network used for behavior cloning
- `FleetMessage`: telemetry sent by each vehicle
- `FleetCoordinator`: central service that stores data and creates alerts

## Project Layout

These are the most important files and folders:

- `main.py`: the only file you normally run directly
- `self_driving/simulator/`: simulator backends
- `self_driving/data/`: dataset recording and loading
- `self_driving/training.py`: training logic
- `self_driving/inference.py`: trained-model driving logic
- `self_driving/networking/`: telemetry client, server, and coordinator
- `docs/`: UML, command, and project documentation

If you want a full file-by-file explanation, open [docs/file_and_command_guide.md](docs/file_and_command_guide.md).

## Current Strengths

The project already supports:

- dataset recording
- behavior-cloning training
- closed-loop inference
- a built-in simulator and a CARLA backend
- telemetry publishing
- SQLite-based fleet coordination
- collision advisories based on proximity and predicted path overlap

## Current Limits

The project is a strong starter system, but it is not a finished autonomous driving platform.

Important limits:

- collision advisories are returned to the client, but they are not yet fused directly into steering or braking
- model quality depends on the quality of the data collected
- a stronger expert driver will improve real training data
- the built-in `mock` simulator is useful for software testing, but real evaluation should happen in CARLA

## Best Way To Read This Project

If you are new to the project, read in this order:

1. `README.md`
2. [docs/file_and_command_guide.md](docs/file_and_command_guide.md)
3. [docs/cli_command_reference.md](docs/cli_command_reference.md)
4. [docs/self_driving_use_case.md](docs/self_driving_use_case.md)
5. [docs/self_driving_uml_final.md](docs/self_driving_uml_final.md)

## Research Direction

The strongest paper topic for this project is:

**Evaluating Shared Telemetry for Cooperative Collision Awareness in a CARLA-Based Autonomous Driving System**

Why this topic fits:

- the project already has a self-driving pipeline
- the project already has telemetry publishing
- the project already has a central coordination service
- the research question is clear: does shared telemetry improve collision awareness?

The paper outline is available in:

- [docs/paper_outline.md](docs/paper_outline.md)
- `docs/paper_outline_google_docs.docx`
