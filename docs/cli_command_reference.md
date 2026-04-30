# CLI Command Reference

This file documents every current command exposed by [main.py](/Users/dylanweaver/Documents/Projects/Carla_Self_Driving/main.py:1), including parameters, defaults, and what each option means.

## Entry Point

Run every command through:

```bash
python3 main.py <command> [options]
```

Current commands:

- `env`
- `demo`
- `collect`
- `train`
- `infer`
- `serve`

## Important CLI Behavior

- If you run `python3 main.py` with no command, the program defaults to `demo`.
- If you run `python3 main.py --some-flag`, the program also treats that as `demo`.
- `python3 main.py --help` therefore shows `demo --help`, not a top-level command list.

## Shared Simulation Parameters

These are used by `demo`, `collect`, and `infer`.

| Flag | Type | Default | Meaning |
| --- | --- | --- | --- |
| `--backend` | `mock` or `carla` | `mock` | Selects the simulator backend. Use `mock` on your Mac. Use `carla` on the CARLA machine. |
| `--steps` | `int` | `120` | Number of control loop iterations to run. |
| `--host` | `string` | `127.0.0.1` | CARLA server host when using `--backend carla`. |
| `--port` | `int` | `2000` | CARLA server port when using `--backend carla`. |
| `--spawn-index` | `int` | `0` | Which CARLA spawn point to use for the ego vehicle. |
| `--vehicle-id` | `string` | `ego-001` | Logical vehicle ID written into telemetry, recordings, and summaries. |
| `--camera-width` | `int` | `160` | Width of the front camera image in pixels. |
| `--camera-height` | `int` | `90` | Height of the front camera image in pixels. |

## Shared Run Parameters

These are used by `demo`, `collect`, and `infer`.

| Flag | Type | Default | Meaning |
| --- | --- | --- | --- |
| `--target-speed` | `float` | `8.0` | Target speed in meters per second for controllers that use speed regulation. |
| `--publish-url` | `string` | `None` | Optional coordinator endpoint, such as `http://127.0.0.1:8765/telemetry`. |
| `--quiet` | flag | `False` | If set, suppresses per-step JSON and only prints the final summary. |

## Command: `env`

Purpose:
- Print local environment details for Python and installed packages.

Syntax:

```bash
python3 main.py env
```

What it prints:
- Python version
- machine architecture
- NumPy version
- OpenCV version
- PyTorch version
- MPS availability
- CARLA API availability

Example:

```bash
python3 main.py env
```

## Command: `demo`

Purpose:
- Run a driving loop without recording a dataset.

Syntax:

```bash
python3 main.py demo [simulation options] [run options] [demo options]
```

Demo-specific parameters:

| Flag | Type | Default | Meaning |
| --- | --- | --- | --- |
| `--controller` | `demo` or `lane` | `demo` | Chooses the controller used during the demo run. |
| `--show-env` | flag | `False` | Print environment details before starting the run. |

Controller definitions:

- `demo`: simple scripted controller
- `lane`: rule-based lane-keeping controller

Example commands:

```bash
python3 main.py demo --backend mock --steps 50
python3 main.py demo --backend mock --controller lane --steps 100 --quiet
python3 main.py demo --backend carla --host 127.0.0.1 --port 2000 --steps 100
```

## Command: `collect`

Purpose:
- Record a driving episode to disk for later training.

Syntax:

```bash
python3 main.py collect [simulation options] [run options] [collect options]
```

Collect-specific parameters:

| Flag | Type | Default | Meaning |
| --- | --- | --- | --- |
| `--controller` | `demo` or `lane` | `None` | If omitted, the system chooses `lane` for `mock` and `demo` for `carla`. |
| `--output` | `string/path` | `None` | Episode output directory. If omitted, the system creates a timestamped folder under `data/episodes/`. |
| `--show-env` | flag | `False` | Print environment details before starting the run. |

Generated output:
- `metadata.json`
- `manifest.jsonl`
- `images/` directory

Example commands:

```bash
python3 main.py collect --backend mock --steps 400
python3 main.py collect --backend mock --controller lane --output data/episodes/mock_run_01
python3 main.py collect --backend carla --steps 1000 --output data/episodes/carla_run_01
```

## Command: `train`

Purpose:
- Train the behavior-cloning model from a collected episode directory.

Syntax:

```bash
python3 main.py train --dataset <episode_dir> [training options]
```

Training parameters:

| Flag | Type | Default | Required | Meaning |
| --- | --- | --- | --- | --- |
| `--dataset` | `string/path` | none | yes | Path to an episode directory created by `collect`. |
| `--output` | `string/path` | `models/driving_model.pt` | no | Where to save the trained model checkpoint. |
| `--epochs` | `int` | `5` | no | Number of training epochs. |
| `--batch-size` | `int` | `16` | no | Batch size used by the data loader. |
| `--learning-rate` | `float` | `0.001` | no | Optimizer learning rate. |
| `--val-split` | `float` | `0.2` | no | Fraction of data used for validation. |
| `--device` | `string` | `None` | no | Torch device override, such as `cpu`, `mps`, or `cuda`. |

Example commands:

```bash
python3 main.py train --dataset data/episodes/mock_run_01
python3 main.py train --dataset data/episodes/mock_run_01 --epochs 10 --batch-size 8
python3 main.py train --dataset data/episodes/carla_run_01 --output models/carla_model.pt --device cuda
```

## Command: `infer`

Purpose:
- Run the trained model in a closed driving loop.

Syntax:

```bash
python3 main.py infer --checkpoint <model_path> [simulation options] [run options] [infer options]
```

Infer-specific parameters:

| Flag | Type | Default | Required | Meaning |
| --- | --- | --- | --- | --- |
| `--checkpoint` | `string/path` | none | yes | Path to the trained model checkpoint. |
| `--output` | `string/path` | `None` | no | If provided, records the inference run as an episode directory. |
| `--show-env` | flag | `False` | no | Print environment details before starting the run. |

Example commands:

```bash
python3 main.py infer --backend mock --checkpoint models/driving_model.pt
python3 main.py infer --backend mock --checkpoint models/driving_model.pt --steps 200 --quiet
python3 main.py infer --backend carla --checkpoint models/carla_model.pt --publish-url http://127.0.0.1:8765/telemetry
```

## Command: `serve`

Purpose:
- Run the central coordination service that receives telemetry and stores it in SQLite.

Syntax:

```bash
python3 main.py serve [server options]
```

Server parameters:

| Flag | Type | Default | Meaning |
| --- | --- | --- | --- |
| `--host` | `string` | `127.0.0.1` | Bind address for the HTTP server. |
| `--port` | `int` | `8765` | Bind port for the HTTP server. |
| `--db` | `string/path` | `data/fleet/fleet.db` | SQLite database path for telemetry storage. |
| `--proximity-threshold` | `float` | `8.0` | Distance threshold, in meters, for proximity alerts. |
| `--stale-after` | `float` | `2.0` | Ignore telemetry older than this many seconds during collision checks. |

Example commands:

```bash
python3 main.py serve
python3 main.py serve --host 0.0.0.0 --port 8765
python3 main.py serve --db data/fleet/test.db --proximity-threshold 5.0 --stale-after 1.5
```

## Typical Workflows

### Local Mac workflow

```bash
python3 main.py env
python3 main.py collect --backend mock --steps 400 --output data/episodes/mock_run_01
python3 main.py train --dataset data/episodes/mock_run_01 --output models/mock_model.pt
python3 main.py infer --backend mock --checkpoint models/mock_model.pt --steps 100
```

### CARLA machine workflow

```bash
python3 main.py demo --backend carla --steps 100
python3 main.py collect --backend carla --steps 1000 --output data/episodes/carla_run_01
python3 main.py train --dataset data/episodes/carla_run_01 --output models/carla_model.pt --device cuda
python3 main.py infer --backend carla --checkpoint models/carla_model.pt --publish-url http://127.0.0.1:8765/telemetry
```

### Fleet coordination workflow

Terminal 1:

```bash
python3 main.py serve --host 0.0.0.0 --port 8765
```

Terminal 2:

```bash
python3 main.py infer --backend carla --checkpoint models/carla_model.pt --publish-url http://127.0.0.1:8765/telemetry
```

## Quick Definitions

- `backend`: which simulator implementation to use
- `checkpoint`: saved trained model file
- `dataset`: recorded episode folder used for training
- `episode`: one recorded driving run containing images and manifest data
- `publish-url`: coordinator server endpoint for telemetry
- `spawn-index`: CARLA map spawn point number
- `target-speed`: desired forward speed for rule-based or model-assisted control
- `telemetry`: shared vehicle state data used for fleet coordination
