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

### 1. Create a Python environment

```bash
python3.12 -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install numpy opencv-python torch
```

If you want to use the real CARLA backend, install the CARLA Python API in the same environment.

### 3. Check the environment

```bash
python3 main.py env
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
python3 main.py demo --backend mock --steps 50
```

Use this when you just want to see the pipeline run without saving data.

### Step 2. Record a dataset

```bash
python3 main.py collect --backend mock --steps 400 --output data/episodes/run_01
```

This creates a dataset folder that contains:

- `metadata.json`
- `manifest.jsonl`
- `images/`

On CARLA, `collect` now defaults to the built-in autopilot teacher so the saved controls are better than the simple demo driver.

### Step 3. Train the model

```bash
python3 main.py train --dataset data/episodes/run_01 --output models/driving_model.pt
```

This trains the model and saves it as `models/driving_model.pt`.

### Step 4. Run the trained model

```bash
python3 main.py infer --backend mock --checkpoint models/driving_model.pt --steps 100
```

This loads the saved model and lets it drive the vehicle.

### Step 5. Start the fleet coordinator

```bash
python3 main.py serve --host 0.0.0.0 --port 8765
```

This starts the central telemetry service.

### Step 6. Drive while publishing telemetry

```bash
python3 main.py infer --backend mock --checkpoint models/driving_model.pt --publish-url http://127.0.0.1:8765/telemetry
```

This runs the car and sends its telemetry to the fleet server.

## The Commands You Should Know

- `env`: check Python and package setup
- `demo`: run the system without saving a dataset
- `collect`: save a driving dataset
- `train`: train the driving model
- `infer`: run the trained model
- `serve`: start the fleet coordination server

The full parameter list is in [docs/cli_command_reference.md](docs/cli_command_reference.md).

## UML Summary In Simple Terms

The formal UML package is in:

- [docs/self_driving_uml_final.md](docs/self_driving_uml_final.md)
- [docs/self_driving_use_case.md](docs/self_driving_use_case.md)

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
