# Carla Self-Driving Car Seminar Project

This repository contains an autonomous-driving research workflow built around the CARLA simulator, behavior-cloning model training in PyTorch, and shared telemetry experiments for cooperative collision awareness.

In practical terms, the project does four main things:

1. Runs vehicles in simulation through either a lightweight mock backend or CARLA.
2. Records camera images, vehicle state, and control commands into reusable datasets.
3. Trains and evaluates a behavior-cloning driving model.
4. Publishes vehicle telemetry to a central coordinator that can generate collision advisories.

## Repository Highlights

- `mock` and `carla` simulator backends for fast local testing and full simulator runs
- dataset recording pipeline with `metadata.json`, `manifest.jsonl`, and image capture
- behavior-cloning training and closed-loop inference in PyTorch
- CARLA autopilot teacher workflow for higher-quality training data
- SQLite-backed fleet coordination service for shared telemetry experiments
- UML, proposal, and research documentation for seminar and graduate-level continuation

## Current Status

The software pipeline is working end-to-end:

- dataset collection works in both mock mode and CARLA
- model training works on CPU, CUDA, and Apple MPS
- trained checkpoints can drive in closed-loop inference
- CARLA autopilot can run as a first-class inference model with no checkpoint
- CARLA inference reports sticky collision, obstacle, and blocked-vehicle diagnostics
- CARLA autopilot can guide inference runs while model controls are logged for comparison
- fleet telemetry can be published to a central coordinator

The latest public checkpoint in this repository is:

- `models/teacherRefined_v1_cuda.pt`

It was fine-tuned from `models/laneRecovery_v1_cuda.pt` using seven CARLA
teacher/recovery datasets, CUDA mixed-precision training, `136000` total
samples, and a `0.1` validation split. Older checkpoints remain useful for
comparison, but the refined teacher checkpoint is the current recommended
CARLA model.

Current limitations:

- driving quality is still strongly dependent on dataset quality and coverage
- collision advisories are generated centrally, but not yet fused directly into vehicle control
- the mock backend is useful for software validation, but CARLA remains the real evaluation target

## Why This Project Matters

A single self-driving vehicle can only react to what it senses locally. That works, but it becomes more limited when traffic is dense, vehicles occlude one another, or multiple actors enter the same space at the same time.

This project explores a second layer on top of the normal autonomy loop: shared telemetry. Vehicles can publish position, heading, speed, and predicted path data to a central coordination service, which can then identify possible path conflicts and generate collision advisories.

That makes the project a strong fit for research on cooperative collision awareness and sim-to-real autonomous systems.

## Research Scope And Continuation

This repository is part of a Seminar research project at William Paterson University. The current team is:

- Dylan Weaver
- Michael

The repository currently focuses on the software side of the work:

- CARLA-based simulation
- data collection
- behavior-cloning model training
- model inference in simulation
- telemetry sharing and central coordination experiments

This project is intended to continue beyond the current Seminar course. The longer-term direction is to extend the work into graduate-level research and a broader sim-to-real autonomous vehicle platform.

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

On Windows, the repo also includes `py.cmd`. When Command Prompt is opened in
this project folder, it lets `py -3.12 ...` run through the project `.venv` even
if the global Windows Python Launcher is not installed.

### Run naming convention

Long timestamped folders still work, but active CARLA collection workflows also
accept short run names such as `10hr2cars_v1`, `5hr2cars_v2`, and
`stopSigns_v1`. The run name is reused for `data\episodes`, `data\raw` TAR
shards, `models`, and `logs` so each chunk stays easy to track.

See [docs/run_naming_scheme.md](docs/run_naming_scheme.md) for copy-paste
examples.

### 1. Create a Python environment

On Windows:

```bash
py -3.12 -m venv .venv
.venv\Scripts\activate
```

On macOS or Linux:

```bash
python3 -m venv .venv
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

Every command section below uses the same format:

- Purpose: what the command is for
- Base command: the shortest shape of the command
- Example commands: copy-paste commands for common project tasks
- Output to check: the most important result to inspect

### Command: `env`

Purpose:
- confirm Python, package, PyTorch, and CARLA API availability

Base command:

```bash
py -3.12 main.py env
```

Output to check:
- `PyTorch`
- `CARLA API`

### Command: `demo`

Purpose:
- run a quick driving loop without saving a dataset

Base command:

```bash
py -3.12 main.py demo [options]
```

Example commands:

```bash
py -3.12 main.py demo --backend mock --steps 50
py -3.12 main.py demo --backend mock --controller lane --steps 100 --quiet
py -3.12 main.py demo --backend carla --steps 100 --spawn-index 1 --target-speed 8 --spectator chase
```

Output to check:
- final JSON summary
- `collision_detected`
- `distance_traveled_m`

### Command: `collect`

Purpose:
- record camera images, vehicle state, and applied controls for later training
- record several CARLA autopilot teacher vehicles at once with `collect-fleet`

Base command:

```bash
py -3.12 main.py collect [options]
```

Example commands:

```bash
py -3.12 main.py collect --backend mock --steps 400 --output data/episodes/run_01
py -3.12 main.py collect --backend carla --controller autopilot --steps 1000 --output data/episodes/carla_run_01 --spectator chase
py -3.12 main.py collect --backend carla --controller autopilot --steps 700000 --output data/episodes/carla_overnight_01 --quiet
```

Output to check:
- `metadata.json`
- `manifest.jsonl`
- `images/`

On CARLA, `collect` defaults to the built-in autopilot teacher when no controller is specified.

### Command: `collect-fleet`

Purpose:
- record 2-3 CARLA autopilot teacher vehicles at the same time for larger overnight datasets

Base command:

```bash
py -3.12 main.py collect-fleet --backend carla [options]
```

Example commands:

```bash
py -3.12 main.py collect-fleet --backend carla --vehicles 3 --spawn-indices 1 8 15 --steps 360000 --output-root data/episodes/carla_fleet_overnight_01 --checkpoint models/teacherRefined_v1_cuda.pt --target-speed 8 --lane-guard --traffic-rule-guard --quiet
scripts\collect_fleet_overnight_windows.bat
```

Output structure:
- `data/episodes/carla_fleet_overnight_01/vehicle_01`
- `data/episodes/carla_fleet_overnight_01/vehicle_02`
- `data/episodes/carla_fleet_overnight_01/vehicle_03`

Use `collect-fleet` instead of starting three separate `collect` terminals. It
keeps CARLA in one synchronized tick loop, records each ego vehicle into its own
episode folder, and avoids multiple Python processes fighting over simulator
timing. Because CARLA autopilot is driving the recorded vehicles, this is the
best overnight source for lane following, traffic-light behavior, stop-sign
behavior, and general road-law examples.

When `--checkpoint` is provided, each recorded vehicle also runs the current
model in the background. CARLA autopilot remains the driver and training label,
while the model prediction is saved as `requested_control` in each manifest row.
That lets the project collect teacher data about where the current model agrees
or disagrees with CARLA's road-following behavior without copying the model's
mistakes as labels.

For repeated improvement, use the iterative fleet script:

```bash
scripts\iterate_fleet_model_windows.bat
```

Each iteration collects three guided CARLA autopilot vehicles, fine-tunes from
the latest checkpoint, and then uses the newly trained checkpoint for the next
collection round. This is useful when the model mostly works but needs more
reliable examples around traffic, stop signs, and recovery cases.

For a quick 5-minute comparison/fine-tune pass, use:

```bash
scripts\quick_iterate_10car_5min_windows.bat
```

That script spawns 10 CARLA autopilot teacher cars at different spawn points,
runs the current checkpoint in the background on every car, writes a
`fleet_summary.json` comparison report, and trains a short fine-tuned checkpoint
from the 10 collected episode folders.

To keep going for several quick rounds, use:

```bash
scripts\continue_quick_10car_iterations_windows.bat
```

It automatically starts from the newest non-epoch
`models/quick10cars5min_v*_cuda.pt` checkpoint if one exists, then chains
each new checkpoint into the next 10-car collection/training round. You can also
pass an explicit starting checkpoint as the first argument.

For a lower-heat stability check before leaving the PC alone, run:

```bash
scripts\stability_test_1hr_windows.bat
```

It uses 6 vehicles, 6 short iterations, `NUM_WORKERS=0`, and logs each collection
and training stage under `logs/`. If that survives and temperatures look good,
use the overnight preset:

```bash
scripts\overnight_stable_iterations_windows.bat
```

The overnight preset keeps the same conservative 6-vehicle load and runs 24
short iterations so a crash only loses the current chunk.

If the 6-vehicle preset still crashes or runs hot, use the ultra-stable presets:

```bash
scripts\ultra_stable_1hr_windows.bat
scripts\overnight_ultra_stable_iterations_windows.bat
```

They use 3 vehicles, shorter 3000-step chunks, 1 training epoch, batch size 64,
and `NUM_WORKERS=0`. For maximum recovery safety, collect one tiny chunk and
stop with:

```bash
scripts\collect_ultra_stable_chunk_windows.bat
```

If overnight still crashes, use the 2-car collect-only mode:

```bash
scripts\overnight_2car_collect_only_windows.bat
```

This only collects short 2-car chunks overnight and does not train inside the
loop. In the morning, train all completed chunks with:

```bash
scripts\train_collected_chunks_windows.bat data\episodes\overnight2cars_v1 models\your_start.pt models\your_next.pt
```

### Command: `train`

Purpose:
- train a behavior-cloning checkpoint from one or more recorded datasets

Base command:

```bash
py -3.12 main.py train --dataset <episode_dir> [options]
```

Example commands:

```bash
py -3.12 main.py train --dataset data/episodes/run_01 --output models/driving_model.pt
py -3.12 main.py train --dataset data/episodes/run_01 data/episodes/run_02 --output models/driving_model.pt --epochs 8 --batch-size 16 --num-workers 6
py -3.12 main.py train --dataset data/episodes/carla_fleet_overnight_01/vehicle_01 data/episodes/carla_fleet_overnight_01/vehicle_02 data/episodes/carla_fleet_overnight_01/vehicle_03 --output models/carla_fleet_teacher_cuda.pt --device cuda --epochs 4 --batch-size 128 --num-workers 8 --val-split 0.1 --log-interval 100
py -3.12 main.py train --dataset data/raw/weekendCombined_v1/weekendCombined_v1 --output models/weekendTarIndex_v1_cuda.pt --device cuda --epochs 4 --batch-size 256 --num-workers 8 --val-split 0.1 --log-interval 100
py -3.12 main.py train --init-checkpoint models/trafficPed1hrBalanced_v1_cuda.pt --dataset data/episodes/laneCorrectionSpawn1Speed4_v1 data/episodes/laneCorrectedGuided_v1 --output models/laneFinetuned_v1_cuda.pt --device cuda --epochs 3 --batch-size 128 --num-workers 8 --learning-rate 0.0001 --val-split 0.1 --log-interval 100
py -3.12 main.py train --init-checkpoint models/laneRecovery_v1_cuda.pt --dataset data/episodes/trafficPed1hr_v1 data/episodes/laneCorrectionSpawn1Speed4_v1 data/episodes/recoveryRightYaw_v1 data/episodes/recoveryLeftYaw_v1 data/episodes/recoveryRightCounter_v1 data/episodes/recoveryLeftCounter_v1 data/episodes/teacherSpawn1_30min_v1 --output models/teacherRefined_v1_cuda.pt --device cuda --epochs 4 --batch-size 128 --num-workers 8 --learning-rate 0.00005 --val-split 0.1 --log-interval 100
```

Output to check:
- final training JSON summary
- `train_loss`
- `val_loss`
- saved checkpoint path

Training settings in plain English:
- `--epochs`: how many times the model goes through the full dataset
- `--batch-size`: how many images the model learns from at one time before it updates itself
- `--num-workers`: how many helper processes load images in parallel during training
- `--learning-rate`: how aggressively the optimizer changes the model each update
- `--init-checkpoint`: starts from an existing model so new data fine-tunes it instead of replacing everything it learned
- `--device`: where training runs, usually `cpu` or `cuda`

### Command: `infer`

Purpose:
- run either a trained checkpoint or CARLA autopilot in the driving loop

Base command:

```bash
py -3.12 main.py infer --checkpoint <model_path> [options]
py -3.12 main.py infer --backend carla --autopilot-model [options]
```

Example commands:

```bash
py -3.12 main.py infer --backend mock --checkpoint models/driving_model.pt --steps 100
py -3.12 main.py infer --backend carla --autopilot-model --steps 3000 --spawn-index 1 --target-speed 8 --spectator chase
py -3.12 main.py infer --backend carla --checkpoint models/weekendTarIndex_v1_cuda.pt --steps 300 --spawn-index 1 --target-speed 4 --spectator chase
py -3.12 main.py infer --backend carla --checkpoint models/laneRecovery_v1_cuda.pt --steps 1000 --spawn-index 1 --target-speed 4 --spectator chase --lane-guard
py -3.12 main.py infer --backend carla --checkpoint models/laneRecovery_v1_cuda.pt --steps 1000 --spawn-index 1 --target-speed 4 --spectator chase --lane-guard --traffic-rule-guard
py -3.12 main.py infer --backend carla --checkpoint models/teacherRefined_v1_cuda.pt --steps 600 --spawn-index 1 --target-speed 4 --spectator chase --lane-guard --traffic-rule-guard
py -3.12 main.py infer --backend carla --checkpoint models/weekendTarIndex_v1_cuda.pt --steps 1000 --spawn-index 1 --target-speed 8 --spectator chase --autopilot-guide --output data/episodes/guidedSpawn1Chase_v1
py -3.12 main.py infer --backend carla --checkpoint models/teacherRefined_v1_cuda.pt --steps 600 --spawn-index 1 --target-speed 4 --spectator chase --autopilot-guide --output data/episodes/testRefinedModel_v1
py -3.12 main.py infer --backend carla --checkpoint models/weekendTarIndex_v1_cuda.pt --steps 3000 --spawn-index 1 --target-speed 8 --spectator hood
py -3.12 main.py infer --backend carla --checkpoint models/laneFinetuned_v1_cuda.pt --steps 4000 --spawn-index 1 --target-speed 4 --spectator chase --autopilot-guide --spawn-lateral-offset 1.0 --spawn-yaw-offset 8 --output data/episodes/recoveryRightYaw_v1
```

Output to check:
- `collision_detected`
- `carla_collision_detected`
- `blocked_detected`
- `closest_obstacle_details`
- `average_abs_lane_offset_m`
- `max_abs_lane_offset_m`
- `average_abs_control_delta` when using `--autopilot-guide`

Use `--spectator chase` for third person. Use `--spectator hood` for a first-person-style view.
Use `--autopilot-model` when you want CARLA's proven Traffic Manager behavior as the active model.
Use `--autopilot-guide` when you want CARLA autopilot to drive safely while the model is compared against it.
Use `--lane-guard` when you want a stable demonstration with CARLA waypoint correction. It softens small corrections inside junctions to avoid twitching, but it applies stronger recovery steering and slows the car when lane offset or heading error gets large. If recovery braking nearly stops the car, the guard crawls slowly so the steering can pull it back into the lane. Leave it off for a pure model-only evaluation.
Use `--traffic-rule-guard` when you want CARLA to assist braking for red/yellow lights and stop signs. The guard can creep a stopped car closer to a red-light trigger line and release leftover braking when the light turns green. Red/yellow light braking applies before the junction; once the car is already inside a junction it should clear the intersection unless an obstacle blocks it. It does not override model-only braking when no active rule is present; fix those false stops with targeted data instead of a throttle override. Leave it off for a pure image-only model evaluation.
Obstacle braking ignores `traffic.*` actors such as traffic lights, and fallback red-light selection is stricter once the car is already inside a junction.
If a visible traffic light or stop sign does not match the logs, check `traffic_rule_details.traffic_light.source` or `traffic_rule_details.stop_sign.source`, plus `id`, `road_id`, and `lane_id`, to see which CARLA actor was selected.
Use `--spawn-lateral-offset` and `--spawn-yaw-offset` with `--autopilot-guide` to collect recovery examples for a model that drifts out of its lane.

### Command: `serve`

Purpose:
- start the fleet telemetry and collision-advisory server

Base command:

```bash
py -3.12 main.py serve [options]
```

Example commands:

```bash
py -3.12 main.py serve
py -3.12 main.py serve --host 0.0.0.0 --port 8765
py -3.12 main.py infer --backend mock --checkpoint models/driving_model.pt --publish-url http://127.0.0.1:8765/telemetry
```

Output to check:
- server startup message
- telemetry POST responses

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
py -3.12 main.py infer --backend carla --checkpoint models/carla_auto_combined_v2.pt --steps 200 --spawn-index 1 --spectator chase
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
- `scripts/collect_fleet_overnight_windows.bat`: records 2-3 CARLA autopilot teacher vehicles at the same time
- `scripts/iterate_fleet_model_windows.bat`: repeats guided fleet collection and fine-tuning for several model-improvement rounds
- `scripts/quick_iterate_10car_5min_windows.bat`: runs 10 guided fleet cars for 5 simulated minutes and trains one quick checkpoint
- `scripts/continue_quick_10car_iterations_windows.bat`: chains several 10-car quick rounds, using each new checkpoint as the next starting model
- `scripts/stability_test_1hr_windows.bat`: conservative 6-car test before unattended overnight runs
- `scripts/overnight_stable_iterations_windows.bat`: conservative 6-car overnight iteration preset
- `scripts/stable_fleet_iterations_windows.bat`: shared configurable runner used by the stable presets
- `scripts/ultra_stable_1hr_windows.bat`: lower-load 3-car test when the stable preset still crashes
- `scripts/overnight_ultra_stable_iterations_windows.bat`: lower-load 3-car overnight preset
- `scripts/collect_ultra_stable_chunk_windows.bat`: one tiny collect-only chunk for maximum crash recovery
- `scripts/overnight_2car_collect_only_windows.bat`: most stable overnight collector, 2 cars and no training loop
- `scripts/train_collected_chunks_windows.bat`: trains all completed chunk folders from a collect-only overnight run
- `scripts/train_overnight_segments_windows.bat`: trains one model from all collected `segment_*` folders
- `scripts/package_segmented_dataset.py`: rewrites many `segment_*` folders into one combined dataset TAR for easier transfer and later training
- `scripts/train_carla_tar_index_windows.bat`: trains from a TAR-indexed CARLA dataset on CUDA
- `scripts/check_training_status_windows.ps1`: checks training process, GPU status, and training log output
- `scripts/collect_traffic_pedestrians_30min_windows.bat`: records one 30-sim-minute CARLA run with traffic and pedestrians

The collection script is safer for long runs because completed segments remain usable even if the machine stops during the night.

For very large CARLA datasets, do not fully extract millions of images unless
there is a specific reason. The preferred workflow is to keep the combined TAR,
build/use the TAR image index, and train from the dataset root that contains
`manifest.jsonl`, `metadata.json`, and `tar_image_index.jsonl`.

On Windows, high-batch TAR training should start with `BATCH_SIZE=512` and
`NUM_WORKERS=4`. If PyTorch reports `RuntimeError: Couldn't open shared file
mapping` with error code `1455`, the GPU is not the problem; Windows ran out of
shared mapping / paging-file headroom for DataLoader workers. Re-run with fewer
workers first, then lower batch size if needed:

```bat
set LEARNING_RATE=0.00001&& set EPOCHS=2&& set BATCH_SIZE=512&& set NUM_WORKERS=4&& scripts\train_tar_shards_fast_windows.bat data\raw\10hr2cars_v1_tar_shards\10hr2cars_v1_datasets.txt models\10hr2cars_v1_cuda.pt models\10hr2cars_v2_cuda.pt
```

## Using CARLA Traffic With This Project

The safest way to add more realistic road behavior is:

- run one ego vehicle from this project
- run background traffic from CARLA's default traffic script
- keep both pointed at the same CARLA host and port

Typical pattern:

### Terminal 1: CARLA traffic script

Run this from the CARLA installation folder if `generate_traffic.py` is available there:

```bash
py -3.12 -m pip install PythonAPI/carla/dist/carla-0.9.16-cp312-cp312-win_amd64.whl
py -3.12 PythonAPI/examples/generate_traffic.py --host 127.0.0.1 --port 2000 --tm-port 8000 --number-of-vehicles 30 --number-of-walkers 60 --safe
```

The install command is only needed once, or whenever `generate_traffic.py`
prints `ModuleNotFoundError: No module named 'carla'`.

### Terminal 2: this project

Run your collection or inference command from this project folder:

```bash
py -3.12 main.py infer --backend carla --checkpoint models/weekendTarIndex_v1_cuda.pt --steps 1000 --spawn-index 1 --target-speed 8 --spectator chase --autopilot-guide
```

For a 30-sim-minute traffic and pedestrian data collection run:

```bash
scripts\collect_traffic_pedestrians_30min_windows.bat
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
