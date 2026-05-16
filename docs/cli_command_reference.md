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
| `collect-fleet` | Save multiple CARLA autopilot teacher datasets at once | Use for overnight multi-car data |
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
| `--spawn-lateral-offset` | `float` | `0.0` | Move the CARLA spawn sideways in meters. Use this to collect lane-recovery data. |
| `--spawn-yaw-offset` | `float` | `0.0` | Rotate the CARLA spawn in degrees. Use this to collect steering-recovery data. |
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

## Command: `collect-fleet`

### What it does

Runs multiple CARLA autopilot teacher vehicles in the same synchronized CARLA
session and records each vehicle as a separate episode folder.

### Good time to use it

Use `collect-fleet` for overnight data collection when you want 2-3 times more
teacher data without starting multiple Python processes.

### Base command

```bash
py -3.12 main.py collect-fleet --backend carla [options]
```

### Extra parameters for `collect-fleet`

| Flag | Type | Default | Simple meaning |
| --- | --- | --- | --- |
| `--vehicles` | `int` | `3` | Number of recorded autopilot vehicles. |
| `--spawn-indices` | `one or more int values` | `1 8 15` | Spawn points to try for the recorded vehicles. |
| `--output-root` | `string/path` | `data/episodes/carla_fleet_overnight` | Root folder containing `vehicle_01`, `vehicle_02`, etc. |
| `--steps` | `int` | `120` | Number of CARLA ticks to record. |
| `--checkpoint` | `string/path` | none | Optional current model to run in the background while CARLA autopilot drives. |
| `--target-speed` | `float` | `8.0` | Target speed passed to the background model. |
| `--lane-guard` | flag | `False` | Apply lane guard to background model predictions. |
| `--traffic-rule-guard` | flag | `False` | Apply traffic-rule guard to background model predictions. |
| `--quiet` | flag | `False` | Suppress progress logs except final summary. |

### Output to check

- `vehicle_01/metadata.json`
- `vehicle_01/manifest.jsonl`
- `vehicle_01/images/`
- matching folders for every other recorded vehicle

### Example commands

```bash
py -3.12 main.py collect-fleet --backend carla --vehicles 2 --spawn-indices 1 8 --steps 36000 --output-root data/episodes/carla_fleet_test_01 --quiet
py -3.12 main.py collect-fleet --backend carla --vehicles 3 --spawn-indices 1 8 15 --steps 360000 --output-root data/episodes/carla_fleet_overnight_01 --checkpoint models/teacherRefined_v1_cuda.pt --target-speed 8 --lane-guard --traffic-rule-guard --quiet
scripts\collect_fleet_overnight_windows.bat
```

Do not run three separate `main.py collect` terminals against the same CARLA
world. `collect-fleet` owns the CARLA tick loop once and records all vehicles
from that shared clock, which is safer for overnight collection.

When `--checkpoint` is set, the dataset still uses CARLA autopilot controls as
the training labels. The current model's predicted controls are stored as
`requested_control`, which is useful for comparing the model against the teacher
without training directly on the model's own mistakes.

For multiple improvement rounds, run:

```bash
scripts\iterate_fleet_model_windows.bat
```

That script alternates between guided 3-car CARLA collection and fine-tuning.
The next collection round uses the checkpoint produced by the previous round.

For a faster smoke-test iteration, run:

```bash
scripts\quick_iterate_10car_5min_windows.bat
```

That script records 10 CARLA autopilot teacher cars for `6000` ticks, which is
5 simulated minutes at the default `0.05` second fixed tick. It also writes
`fleet_summary.json` with average and maximum control deltas between the current
model and CARLA autopilot.

To chain several quick rounds:

```bash
scripts\continue_quick_10car_iterations_windows.bat
```

The continuation script auto-starts from the newest non-epoch quick checkpoint
unless a checkpoint path is passed as its first argument.

For a cooler stability test before an unattended run:

```bash
scripts\stability_test_1hr_windows.bat
```

If the 1-hour preset is stable and temperatures stay reasonable, use:

```bash
scripts\overnight_stable_iterations_windows.bat
```

Both stable presets use the shared `stable_fleet_iterations_windows.bat` runner,
6 vehicles, `NUM_WORKERS=0`, and per-iteration logs under `logs/`.

If that still crashes or runs too hot, use:

```bash
scripts\ultra_stable_1hr_windows.bat
scripts\overnight_ultra_stable_iterations_windows.bat
```

The ultra presets use 3 vehicles, 3000-step chunks, 1 epoch, batch size 64, and
`NUM_WORKERS=0`. The safest possible mode is:

```bash
scripts\collect_ultra_stable_chunk_windows.bat
```

That collects one tiny chunk and exits, then prints the train command to run.

For the most stable overnight option, separate collection from training:

```bash
scripts\overnight_2car_collect_only_windows.bat
```

It collects 2-car chunks and does not train during the loop. Train completed
chunks later with:

```bash
scripts\train_collected_chunks_windows.bat data\episodes\overnight2cars_v1 models\start.pt models\next.pt
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
| `--init-checkpoint` | `string/path` | none | no | Existing checkpoint to start from before training. Use this to fine-tune instead of training from scratch. |
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
| `--init-checkpoint` | Existing model weights to start from. | Use this when correcting a mostly good model with new guided data. |
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
- large CUDA TAR-index run: `--epochs 2 --batch-size 512 --num-workers 4 --device cuda --val-split 0.1`
- fine-tune correction run: `--init-checkpoint models/trafficPed1hrBalanced_v1_cuda.pt --epochs 3 --learning-rate 0.0001 --device cuda`
- refined teacher run: `--init-checkpoint models/laneRecovery_v1_cuda.pt --epochs 4 --batch-size 128 --learning-rate 0.00005 --device cuda --val-split 0.1`

### Example commands

```bash
py -3.12 main.py train --dataset data/episodes/mock_run_01
py -3.12 main.py train --dataset data/episodes/mock_run_01 --epochs 10 --batch-size 8
py -3.12 main.py train --dataset data/episodes/carla_run_01 data/episodes/carla_run_02 --output models/carla_combined.pt --num-workers 4
py -3.12 main.py train --dataset data/episodes/carla_run_01 --output models/carla_run_01_cuda.pt --device cuda
py -3.12 main.py train --dataset data/episodes/carla_fleet_overnight_01/vehicle_01 data/episodes/carla_fleet_overnight_01/vehicle_02 data/episodes/carla_fleet_overnight_01/vehicle_03 --output models/carla_fleet_teacher_cuda.pt --device cuda --epochs 4 --batch-size 128 --num-workers 8 --val-split 0.1 --log-interval 100
py -3.12 main.py train --dataset data/raw/weekendCombined_v1/weekendCombined_v1 --output models/weekendTarIndex_v1_cuda.pt --device cuda --epochs 4 --batch-size 256 --num-workers 8 --val-split 0.1 --log-interval 100
py -3.12 main.py train --init-checkpoint models/trafficPed1hrBalanced_v1_cuda.pt --dataset data/episodes/laneCorrectionSpawn1Speed4_v1 data/episodes/laneCorrectedGuided_v1 --output models/laneFinetuned_v1_cuda.pt --device cuda --epochs 3 --batch-size 128 --num-workers 8 --learning-rate 0.0001 --val-split 0.1 --log-interval 100
py -3.12 main.py train --init-checkpoint models/laneRecovery_v1_cuda.pt --dataset data/episodes/trafficPed1hr_v1 data/episodes/laneCorrectionSpawn1Speed4_v1 data/episodes/recoveryRightYaw_v1 data/episodes/recoveryLeftYaw_v1 data/episodes/recoveryRightCounter_v1 data/episodes/recoveryLeftCounter_v1 data/episodes/teacherSpawn1_30min_v1 --output models/teacherRefined_v1_cuda.pt --device cuda --epochs 4 --batch-size 128 --num-workers 8 --learning-rate 0.00005 --val-split 0.1 --log-interval 100
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
| `--lane-guard` | flag | `False` | no | CARLA waypoint safety assist nudges steering back toward the lane if the model drifts. |
| `--lane-guard-strength` | `float` | `0.55` | no | Maximum normal steering blend used by `--lane-guard`. Large recovery errors can override this for safety. |
| `--traffic-rule-guard` | flag | `False` | no | CARLA rule assist brakes for detected red/yellow lights and stop signs. |
| `--show-env` | flag | `False` | no | Print environment details before the run starts. |

### Example commands

```bash
py -3.12 main.py infer --backend mock --checkpoint models/driving_model.pt
py -3.12 main.py infer --backend mock --checkpoint models/driving_model.pt --steps 200 --quiet
py -3.12 main.py infer --backend carla --autopilot-model --steps 3000 --spawn-index 1 --target-speed 8 --spectator chase
py -3.12 main.py infer --backend carla --checkpoint models/weekendTarIndex_v1_cuda.pt --publish-url http://127.0.0.1:8765/telemetry --spectator chase
py -3.12 main.py infer --backend carla --checkpoint models/weekendTarIndex_v1_cuda.pt --steps 300 --spawn-index 1 --target-speed 4 --spectator chase
py -3.12 main.py infer --backend carla --checkpoint models/laneRecovery_v1_cuda.pt --steps 1000 --spawn-index 1 --target-speed 4 --spectator chase --lane-guard
py -3.12 main.py infer --backend carla --checkpoint models/laneRecovery_v1_cuda.pt --steps 1000 --spawn-index 1 --target-speed 4 --spectator chase --lane-guard --traffic-rule-guard
py -3.12 main.py infer --backend carla --checkpoint models/teacherRefined_v1_cuda.pt --steps 600 --spawn-index 1 --target-speed 4 --spectator chase --lane-guard --traffic-rule-guard
py -3.12 main.py infer --backend carla --checkpoint models/weekendTarIndex_v1_cuda.pt --steps 3000 --spawn-index 1 --target-speed 8 --spectator hood
py -3.12 main.py infer --backend carla --checkpoint models/weekendTarIndex_v1_cuda.pt --steps 1000 --spawn-index 1 --target-speed 8 --spectator chase --autopilot-guide --output data/episodes/guidedSpawn1Chase_v1
py -3.12 main.py infer --backend carla --checkpoint models/teacherRefined_v1_cuda.pt --steps 600 --spawn-index 1 --target-speed 4 --spectator chase --autopilot-guide --output data/episodes/testRefinedModel_v1
```

The final inference summary includes run-quality metrics such as
`distance_traveled_m`, `average_speed_mps`, `max_speed_mps`,
`average_throttle`, and `average_brake`. In CARLA, collision reporting is
sticky for the full run: if the car hits something and later stops reporting a
live collision event, the final `collision_detected` value still stays `true`.
The summary can also include `first_collision_details`,
`last_collision_details`, `closest_obstacle_details`, `blocked_detected`,
`average_abs_lane_offset_m`, and `max_abs_lane_offset_m`.
With `--autopilot-model`, CARLA Traffic Manager owns the driving controls.
With `--autopilot-guide`, the summary also includes
`average_abs_control_delta` and `max_abs_control_delta`, which show how far the
model's predictions were from CARLA autopilot's applied controls.
Use `--lane-guard` when you want a stable CARLA demonstration with a trained
checkpoint plus a light map-based lane correction. The correction is damped
inside junctions to avoid twitching when CARLA waypoints change through an
intersection, but large lane or heading errors trigger stronger recovery
steering and speed reduction. If recovery braking nearly stops the car, the
guard crawls slowly so the steering can pull it back into the lane. Leave it
off when you want a pure model-only evaluation.
Use `--traffic-rule-guard` with CARLA when you want a safety assist for
traffic lights and stop signs. The guard can creep a stopped car closer to a
red-light trigger line, then release leftover braking when the light turns
green. It does not override model-only braking when no active rule is present;
fix those false stops with targeted data instead of a throttle override. Leave
it off when you want to measure whether the image-only model learned those
rules by itself.
Obstacle braking ignores `traffic.*` actors such as traffic lights, and
fallback red-light selection is stricter once the car is already inside a
junction.
If the visible light or stop sign disagrees with the log, inspect
`traffic_rule_details.traffic_light.source` or
`traffic_rule_details.stop_sign.source`, plus `id`, `road_id`, and `lane_id`,
to confirm which CARLA actor was selected.

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
py -3.12 main.py infer --backend carla --checkpoint models/weekendTarIndex_v1_cuda.pt --steps 300 --spawn-index 1 --target-speed 4 --spectator chase
py -3.12 main.py infer --backend carla --checkpoint models/teacherRefined_v1_cuda.pt --steps 600 --spawn-index 1 --target-speed 4 --spectator chase --lane-guard --traffic-rule-guard
py -3.12 main.py infer --backend carla --checkpoint models/weekendTarIndex_v1_cuda.pt --steps 1000 --spawn-index 1 --target-speed 8 --spectator chase --autopilot-guide --output data/episodes/guidedSpawn1Chase_v1
```

A large TAR-indexed dataset can be trained from a dataset root such as:

```text
data/raw/weekendCombined_v1/weekendCombined_v1
```

When using a TAR-indexed dataset, keep the source TAR because the index points
into it and is not a copy of the images.

On Windows, prefer `NUM_WORKERS=4` for high-batch TAR training. `NUM_WORKERS=8`
or `10` can push PyTorch into `RuntimeError: Couldn't open shared file mapping`
with error code `1455`, especially near validation or epoch boundaries. That
means Windows could not allocate another shared mapping for DataLoader workers.
Retry with `NUM_WORKERS=4`; if it still fails, use `BATCH_SIZE=256`.

### Workflow 3: Run one ego vehicle with CARLA background traffic and pedestrians

Use this when you want your model or autopilot car to drive in a busier CARLA world without running multiple copies of `main.py`.

Terminal 1, from the CARLA installation folder:

```bash
py -3.12 -m pip install PythonAPI/carla/dist/carla-0.9.16-cp312-cp312-win_amd64.whl
py -3.12 PythonAPI/examples/generate_traffic.py --host 127.0.0.1 --port 2000 --tm-port 8000 --number-of-vehicles 30 --number-of-walkers 60 --safe
```

The install command is only needed once, or whenever `generate_traffic.py`
prints `ModuleNotFoundError: No module named 'carla'`.

Terminal 2, from this project folder:

```bash
py -3.12 main.py infer --backend carla --autopilot-model --steps 5000 --spawn-index 1 --target-speed 8 --spectator chase
```

For a 30-sim-minute guided data collection run, use:

```bash
py -3.12 main.py infer --backend carla --checkpoint models/weekendTarIndex_v1_cuda.pt --steps 36000 --spawn-index 1 --target-speed 8 --spectator chase --autopilot-guide --output data/episodes/trafficPed30min_v1 --quiet
```

For lane-recovery data, start the ego vehicle slightly offset or angled, then
let `--autopilot-guide` recover while the model predicts in the background:

```bash
py -3.12 main.py infer --backend carla --checkpoint models/laneFinetuned_v1_cuda.pt --steps 4000 --spawn-index 1 --target-speed 4 --spectator chase --autopilot-guide --spawn-lateral-offset 1.0 --spawn-yaw-offset 8 --output data/episodes/recovery_right_yaw_01
py -3.12 main.py infer --backend carla --checkpoint models/laneFinetuned_v1_cuda.pt --steps 4000 --spawn-index 1 --target-speed 4 --spectator chase --autopilot-guide --spawn-lateral-offset -1.0 --spawn-yaw-offset -8 --output data/episodes/recovery_left_yaw_01
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
py -3.12 main.py infer --backend carla --checkpoint models/weekendTarIndex_v1_cuda.pt --publish-url http://127.0.0.1:8765/telemetry --spectator chase --autopilot-guide
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
