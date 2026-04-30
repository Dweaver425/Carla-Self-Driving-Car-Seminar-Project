# Carla Self-Driving Car Seminar Project

## Project Overview

This project studies a self-driving vehicle workflow inside the CARLA simulator. The system is designed to:

- collect driving data from a simulated vehicle,
- train a driving model from recorded episodes,
- run closed-loop autonomous driving,
- publish fleet telemetry to a central coordination service,
- and support collision-awareness through shared vehicle state.

The project combines autonomous driving, machine learning, simulation, and distributed coordination into one research-oriented pipeline.

## Project Goals

The main goals of the project are:

1. Build a simulated self-driving vehicle pipeline.
2. Record sensor and control data for training.
3. Train a behavior-cloning model that predicts steering, throttle, and brake.
4. Test the trained model in autonomous simulation runs.
5. Share vehicle telemetry with a central fleet database.
6. Explore how shared telemetry can improve collision avoidance between multiple vehicles.

## System Workflow

The overall workflow of the project is:

1. Configure and start a simulation run.
2. Collect a dataset of images, vehicle state, and control commands.
3. Train the driving model on the recorded dataset.
4. Run autonomous inference with the trained model.
5. Publish telemetry to the fleet coordinator.
6. Detect possible collisions from nearby vehicles and predicted paths.
7. Store logs, recordings, and model outputs for analysis.

## UML Highlights

The full UML package is available in:

- [Full UML Specification](docs/self_driving_uml_final.md)
- [Use Case Diagram](docs/self_driving_use_case.md)
- [CLI Command Reference](docs/cli_command_reference.md)

The most important UML parts are:

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

### Core System Components

- `SimulationConfig`: stores runtime settings
- `SimulatorClient`: abstract simulator interface
- `MockSimulatorClient`: lightweight simulator backend
- `CarlaSimulatorClient`: CARLA backend
- `LaneKeepingController`: rule-based controller
- `ModelController`: trained-model controller
- `DrivingObservation`: camera frame plus state information
- `EpisodeRecorder`: saves dataset runs
- `DrivingDataset`: loads training data
- `DrivingModel`: neural network for behavior cloning
- `FleetMessage`: telemetry message passed across the fleet
- `FleetCoordinator`: central SQLite-backed coordination service

## Project Structure

- `main.py`: main command-line entrypoint
- `self_driving/simulator/`: simulation backends
- `self_driving/data/`: dataset loading and recording
- `self_driving/training.py`: model training pipeline
- `self_driving/inference.py`: autonomous inference controller
- `self_driving/networking/`: telemetry client, server, and coordinator
- `docs/`: UML and command documentation

## Setup

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

### 3. Verify the environment

```bash
python3 main.py env
```

This prints:

- Python version
- machine architecture
- NumPy version
- OpenCV version
- PyTorch version
- CARLA API availability

## How To Use The Project

### Step 1. Run a basic simulation

```bash
python3 main.py demo --backend mock --steps 50
```

This runs the control loop without recording a dataset.

### Step 2. Collect a dataset

```bash
python3 main.py collect --backend mock --steps 400 --output data/episodes/run_01
```

This creates:

- `data/episodes/run_01/metadata.json`
- `data/episodes/run_01/manifest.jsonl`
- `data/episodes/run_01/images/`

### Step 3. Train the model

```bash
python3 main.py train --dataset data/episodes/run_01 --output models/driving_model.pt
```

This trains the behavior-cloning model and writes the checkpoint to `models/driving_model.pt`.

### Step 4. Run autonomous inference

```bash
python3 main.py infer --backend mock --checkpoint models/driving_model.pt --steps 100
```

This loads the trained model and runs closed-loop autonomous driving.

### Step 5. Start the fleet coordinator

```bash
python3 main.py serve --host 0.0.0.0 --port 8765
```

This starts the central telemetry and collision-coordination service backed by SQLite.

### Step 6. Run a vehicle with telemetry publishing

```bash
python3 main.py infer --backend mock --checkpoint models/driving_model.pt --publish-url http://127.0.0.1:8765/telemetry
```

This sends vehicle telemetry to the coordinator while the vehicle is driving.

## Important Commands

### Environment

```bash
python3 main.py env
```

### Demo run

```bash
python3 main.py demo --backend mock --controller lane --steps 100
```

### Collect dataset

```bash
python3 main.py collect --backend mock --steps 400 --output data/episodes/run_01
```

### Train model

```bash
python3 main.py train --dataset data/episodes/run_01 --epochs 5 --batch-size 16
```

### Inference run

```bash
python3 main.py infer --backend mock --checkpoint models/driving_model.pt --steps 100
```

### Start coordinator

```bash
python3 main.py serve --db data/fleet/fleet.db
```

## What The Project Currently Supports

- dataset recording
- behavior-cloning training
- closed-loop inference
- local or CARLA-backed simulation structure
- telemetry publishing
- SQLite-based fleet coordination
- collision advisory generation from proximity and predicted path overlap

## Current Limitations

- the fleet advisory is returned to the client, but it is not yet fused directly into steering or braking decisions
- data quality depends on the controller used during collection
- a stronger expert driver is still needed for higher-quality CARLA training data

## Documentation

- [Full UML Specification](docs/self_driving_uml_final.md)
- [Use Case Diagram](docs/self_driving_use_case.md)
- [CLI Command Reference](docs/cli_command_reference.md)

## Research Direction

This project is well suited for a paper on cooperative autonomous driving.

The strongest research topic for this codebase is:

**Using Shared Fleet Telemetry to Improve Collision Awareness in a CARLA-Based Autonomous Driving System**

That topic fits the project because it connects:

- self-driving inference,
- central telemetry exchange,
- multi-vehicle coordination,
- and collision reduction.

Possible research questions:

1. Does shared vehicle telemetry improve collision awareness compared to local-only control?
2. How much does predicted-path sharing help compared to sharing only current position and speed?
3. What are the tradeoffs between centralized coordination and purely local decision-making in CARLA?
4. How sensitive is collision avoidance performance to stale or delayed telemetry?

Possible alternative paper titles:

- `Cooperative Collision Awareness for Simulated Autonomous Vehicles Using Shared Telemetry`
- `Centralized Fleet Coordination for Multi-Vehicle Safety in CARLA`
- `Evaluating Telemetry-Assisted Collision Avoidance in a Self-Driving Simulation Pipeline`
