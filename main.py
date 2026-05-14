from __future__ import annotations

import argparse
import importlib
import json
import platform
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from self_driving.config import SimulationConfig
from self_driving.control import AutopilotController, DemoController, LaneKeepingController
from self_driving.data.recording import EpisodeRecorder
from self_driving.inference import ModelController
from self_driving.networking.client import TelemetryPublisher
from self_driving.networking.server import serve_coordinator
from self_driving.pipeline import run_loop
from self_driving.simulator.carla_adapter import CarlaSimulatorClient
from self_driving.simulator.mock import MockSimulatorClient
from self_driving.training import TrainingConfig, train_model

COMMAND_NAMES = {"env", "demo", "collect", "train", "infer", "serve"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Self-driving starter project with mock and CARLA simulator backends."
    )
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("env", help="Print the local Python and package environment.")

    demo_parser = subparsers.add_parser("demo", help="Run a driving loop without recording.")
    add_simulation_arguments(demo_parser)
    add_run_arguments(demo_parser)
    demo_parser.add_argument(
        "--controller",
        choices=("demo", "lane", "autopilot"),
        default="demo",
        help="Controller used for the demo loop.",
    )
    demo_parser.add_argument("--show-env", action="store_true", help="Print environment details.")

    collect_parser = subparsers.add_parser("collect", help="Record a driving episode to disk.")
    add_simulation_arguments(collect_parser)
    add_run_arguments(collect_parser)
    collect_parser.add_argument(
        "--controller",
        choices=("demo", "lane", "autopilot"),
        default=None,
        help="Controller used to generate training data. Defaults to 'lane' on mock and 'autopilot' on CARLA.",
    )
    collect_parser.add_argument(
        "--output",
        default=None,
        help="Episode output directory. Defaults to a timestamped folder under data/episodes.",
    )
    collect_parser.add_argument("--show-env", action="store_true", help="Print environment details.")

    train_parser = subparsers.add_parser("train", help="Train a behavior-cloning model.")
    train_parser.add_argument(
        "--dataset",
        nargs="+",
        required=True,
        help="One or more episode directories created by the collect command.",
    )
    train_parser.add_argument(
        "--output",
        default="models/driving_model.pt",
        help="Checkpoint path for the trained model.",
    )
    train_parser.add_argument(
        "--init-checkpoint",
        default=None,
        help="Optional checkpoint to start from before training. Use this for fine-tuning.",
    )
    train_parser.add_argument("--epochs", type=int, default=5, help="Number of training epochs.")
    train_parser.add_argument("--batch-size", type=int, default=16, help="Batch size.")
    train_parser.add_argument("--learning-rate", type=float, default=1e-3, help="Optimizer LR.")
    train_parser.add_argument(
        "--val-split",
        type=float,
        default=0.2,
        help="Validation fraction between 0.0 and 0.5.",
    )
    train_parser.add_argument(
        "--device",
        default=None,
        help="Torch device override, for example cpu, mps, or cuda.",
    )
    train_parser.add_argument(
        "--num-workers",
        type=int,
        default=0,
        help="Number of parallel data-loading workers used during training.",
    )
    train_parser.add_argument(
        "--log-interval",
        type=int,
        default=100,
        help="Print training speed and loss every N batches. Use 0 to disable.",
    )

    infer_parser = subparsers.add_parser("infer", help="Run a trained model in the loop.")
    add_simulation_arguments(infer_parser)
    add_run_arguments(infer_parser)
    infer_parser.add_argument(
        "--checkpoint",
        default=None,
        help="Model checkpoint path. Required unless --autopilot-model is used.",
    )
    infer_parser.add_argument(
        "--output",
        default=None,
        help="Optional episode directory to record the inference run.",
    )
    infer_parser.add_argument(
        "--autopilot-guide",
        action="store_true",
        help=(
            "With the CARLA backend, let CARLA autopilot drive while the model "
            "still predicts controls for comparison."
        ),
    )
    infer_parser.add_argument(
        "--autopilot-model",
        action="store_true",
        help=(
            "With the CARLA backend, use CARLA autopilot as the active driving "
            "model. No checkpoint is required."
        ),
    )
    infer_parser.add_argument("--show-env", action="store_true", help="Print environment details.")

    serve_parser = subparsers.add_parser(
        "serve",
        help="Run a simple central telemetry and collision-coordination service.",
    )
    serve_parser.add_argument("--host", default="127.0.0.1", help="Bind host.")
    serve_parser.add_argument("--port", type=int, default=8765, help="Bind port.")
    serve_parser.add_argument(
        "--db",
        default="data/fleet/fleet.db",
        help="SQLite database path for fleet telemetry.",
    )
    serve_parser.add_argument(
        "--proximity-threshold",
        type=float,
        default=8.0,
        help="Distance threshold in meters for proximity alerts.",
    )
    serve_parser.add_argument(
        "--stale-after",
        type=float,
        default=2.0,
        help="Ignore telemetry older than this many seconds for collision checks.",
    )

    return parser


def add_simulation_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--backend",
        choices=("mock", "carla"),
        default="mock",
        help="Select the simulator backend: 'mock' or 'carla'.",
    )
    parser.add_argument("--steps", type=int, default=120, help="Number of control steps to run.")
    parser.add_argument("--host", default="127.0.0.1", help="CARLA host.")
    parser.add_argument("--port", type=int, default=2000, help="CARLA port.")
    parser.add_argument(
        "--tm-port",
        type=int,
        default=8000,
        help="CARLA Traffic Manager port used for autopilot.",
    )
    parser.add_argument(
        "--spawn-index",
        type=int,
        default=0,
        help="Spawn point index when using the CARLA backend.",
    )
    parser.add_argument(
        "--spawn-lateral-offset",
        type=float,
        default=0.0,
        help="Move the CARLA spawn point sideways in meters. Useful for recovery-data collection.",
    )
    parser.add_argument(
        "--spawn-yaw-offset",
        type=float,
        default=0.0,
        help="Rotate the CARLA spawn point in degrees. Useful for recovery-data collection.",
    )
    parser.add_argument(
        "--vehicle-id",
        default="ego-001",
        help="Logical vehicle id used in recordings and telemetry.",
    )
    parser.add_argument(
        "--camera-width",
        type=int,
        default=160,
        help="Front camera width in pixels.",
    )
    parser.add_argument(
        "--camera-height",
        type=int,
        default=90,
        help="Front camera height in pixels.",
    )
    parser.add_argument(
        "--spectator",
        choices=("none", "chase", "hood"),
        default="none",
        help="Move CARLA's spectator camera with the ego vehicle.",
    )


def add_run_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--target-speed",
        type=float,
        default=8.0,
        help="Controller target speed in meters per second where relevant.",
    )
    parser.add_argument(
        "--publish-url",
        default=None,
        help="Optional central coordinator URL, for example http://127.0.0.1:8765/telemetry.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress per-step JSON payloads and only print the summary.",
    )


def print_environment() -> None:
    print("Python version:")
    print(sys.version)
    print()
    print("Machine:")
    print(platform.machine())
    print()

    modules = (
        ("NumPy", "numpy"),
        ("OpenCV", "cv2"),
        ("PyTorch", "torch"),
        ("CARLA API", "carla"),
    )
    for label, module_name in modules:
        try:
            module = importlib.import_module(module_name)
        except ImportError:
            print(f"{label}: not installed")
            continue

        version = getattr(module, "__version__", "available")
        print(f"{label}: {version}")

        if module_name == "torch":
            print("MPS available:", module.backends.mps.is_available())


def default_output_dir(category: str, backend: str, controller_name: str) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path("data") / category / f"{timestamp}_{backend}_{controller_name}"


def build_config(args: argparse.Namespace) -> SimulationConfig:
    return SimulationConfig(
        backend=args.backend,
        host=args.host,
        port=args.port,
        traffic_manager_port=args.tm_port,
        spawn_index=args.spawn_index,
        spawn_lateral_offset_m=args.spawn_lateral_offset,
        spawn_yaw_offset_deg=args.spawn_yaw_offset,
        steps=args.steps,
        ego_vehicle_id=args.vehicle_id,
        camera_width=args.camera_width,
        camera_height=args.camera_height,
        spectator_mode=args.spectator,
    )


def make_client(config: SimulationConfig) -> MockSimulatorClient | CarlaSimulatorClient:
    if config.backend == "mock":
        return MockSimulatorClient(config)
    if config.backend == "carla":
        return CarlaSimulatorClient(config)
    raise ValueError(f"Unsupported backend: {config.backend}")


def make_controller(args: argparse.Namespace, controller_name: str) -> Any:
    if controller_name == "demo":
        return DemoController()
    if controller_name == "lane":
        return LaneKeepingController(target_speed_mps=args.target_speed)
    if controller_name == "autopilot":
        if args.backend != "carla":
            raise ValueError("The autopilot controller is only available with the CARLA backend.")
        return AutopilotController()
    if controller_name == "model":
        autopilot_guide = getattr(args, "autopilot_guide", False)
        if autopilot_guide and args.backend != "carla":
            raise ValueError("Autopilot guidance is only available with the CARLA backend.")
        if args.checkpoint is None:
            raise ValueError("The infer command requires --checkpoint unless --autopilot-model is used.")
        return ModelController(
            checkpoint_path=args.checkpoint,
            target_speed_mps=args.target_speed,
            autopilot_guide=autopilot_guide,
        )
    raise ValueError(f"Unsupported controller: {controller_name}")


def maybe_publisher(publish_url: str | None) -> TelemetryPublisher | None:
    if publish_url is None:
        return None
    return TelemetryPublisher(publish_url)


def handle_drive(
    args: argparse.Namespace,
    controller_name: str,
    recorder: EpisodeRecorder | None = None,
) -> None:
    if getattr(args, "show_env", False):
        print_environment()
        print()

    config = build_config(args)
    client = make_client(config)
    controller = make_controller(args, controller_name)
    publisher = maybe_publisher(args.publish_url)

    # All driving modes share the same runtime loop; the only things that change
    # are the simulator backend, the controller, and whether we record/publish.
    summary = run_loop(
        client=client,
        controller=controller,
        steps=config.steps,
        recorder=recorder,
        publisher=publisher,
        print_payload=not args.quiet,
    )
    print(json.dumps(summary, sort_keys=True))


def handle_collect(args: argparse.Namespace) -> None:
    # The mock backend has lane signals, so it can use the lane controller.
    # The CARLA path now defaults to native autopilot so recorded labels follow the road.
    controller_name = args.controller or ("lane" if args.backend == "mock" else "autopilot")
    output_dir = Path(args.output) if args.output else default_output_dir(
        "episodes", args.backend, controller_name
    )
    recorder = EpisodeRecorder(output_dir=output_dir, config=build_config(args), controller_name=controller_name)
    handle_drive(args, controller_name=controller_name, recorder=recorder)


def handle_train(args: argparse.Namespace) -> None:
    summary = train_model(
        TrainingConfig(
            dataset_dirs=[Path(path) for path in args.dataset],
            output_path=Path(args.output),
            init_checkpoint_path=Path(args.init_checkpoint)
            if args.init_checkpoint is not None
            else None,
            epochs=args.epochs,
            batch_size=args.batch_size,
            learning_rate=args.learning_rate,
            val_split=args.val_split,
            device=args.device,
            num_workers=args.num_workers,
            log_interval=args.log_interval,
        )
    )
    print(json.dumps(summary, sort_keys=True))


def handle_serve(args: argparse.Namespace) -> None:
    serve_coordinator(
        host=args.host,
        port=args.port,
        db_path=Path(args.db),
        proximity_threshold_m=args.proximity_threshold,
        stale_after_seconds=args.stale_after,
    )


def normalize_argv(argv: list[str]) -> list[str]:
    # Treat bare flags like `--help` as demo flags so the CLI behaves like a
    # single-purpose app unless the user names a subcommand explicitly.
    if not argv:
        return ["demo"]
    if argv[0] in COMMAND_NAMES:
        return argv
    if argv[0].startswith("-"):
        return ["demo", *argv]
    return argv


def main() -> None:
    argv = normalize_argv(sys.argv[1:])
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "env":
            print_environment()
            return
        if args.command == "demo":
            handle_drive(args, controller_name=args.controller)
            return
        if args.command == "collect":
            handle_collect(args)
            return
        if args.command == "train":
            handle_train(args)
            return
        if args.command == "infer":
            if args.autopilot_model and args.backend != "carla":
                raise ValueError("The --autopilot-model option is only available with the CARLA backend.")
            if args.autopilot_model and args.autopilot_guide:
                raise ValueError("Use either --autopilot-model or --autopilot-guide, not both.")
            if not args.autopilot_model and args.checkpoint is None:
                raise ValueError("The infer command requires --checkpoint unless --autopilot-model is used.")

            controller_name = "autopilot" if args.autopilot_model else "model"
            recorder = None
            if args.output is not None:
                if args.autopilot_model:
                    recorder_controller_name = "autopilot_model"
                elif args.autopilot_guide:
                    recorder_controller_name = "model_autopilot_guide"
                else:
                    recorder_controller_name = "model"
                recorder = EpisodeRecorder(
                    output_dir=Path(args.output),
                    config=build_config(args),
                    controller_name=recorder_controller_name,
                )
            handle_drive(args, controller_name=controller_name, recorder=recorder)
            return
        if args.command == "serve":
            handle_serve(args)
            return
        raise SystemExit("No command selected.")
    except (RuntimeError, FileNotFoundError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()
