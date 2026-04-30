# CARLA Self-Driving Starter

This project is structured so you can develop on macOS with a mock simulator and move the same scripts to a CARLA machine later.

## Main flows

- `python3 main.py demo --backend mock`
- `python3 main.py collect --backend mock --steps 400`
- `python3 main.py train --dataset data/episodes/<episode_dir> --output models/driving_model.pt`
- `python3 main.py infer --backend mock --checkpoint models/driving_model.pt`
- `python3 main.py serve --host 0.0.0.0 --port 8765`

## Architecture

- `self_driving/simulator/mock.py`: local mock simulator with a synthetic front camera.
- `self_driving/simulator/carla_adapter.py`: CARLA runtime backend with an attached RGB camera and collision sensor.
- `self_driving/data/recording.py`: episode recorder that writes images plus a JSONL manifest.
- `self_driving/training.py`: behavior-cloning training loop in PyTorch.
- `self_driving/inference.py`: model-based controller for closed-loop inference.
- `self_driving/networking/server.py`: central telemetry service backed by SQLite.

## Notes

- Use `--backend mock` on your Mac.
- Use `--backend carla` only on the machine with the CARLA Python API installed.
- The central coordinator is advisory. Local sensing and control should remain the safety-critical path.
