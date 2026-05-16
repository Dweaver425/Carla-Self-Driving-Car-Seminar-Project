from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


CONTROL_KEYS = ("throttle", "steering", "brake")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare recorded CARLA teacher controls against shadow model controls."
    )
    parser.add_argument(
        "--dataset-root",
        required=True,
        type=Path,
        help="A run root, chunk folder, or vehicle episode folder containing manifest.jsonl files.",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=None,
        help="Optional path to save the JSON summary.",
    )
    parser.add_argument("--brake-threshold", type=float, default=0.05)
    parser.add_argument("--throttle-threshold", type=float, default=0.05)
    parser.add_argument("--steering-threshold", type=float, default=0.15)
    parser.add_argument("--top-k", type=int, default=10)
    return parser.parse_args()


def discover_episode_dirs(root: Path) -> list[Path]:
    if (root / "manifest.jsonl").exists():
        return [root]
    return sorted(path.parent for path in root.rglob("manifest.jsonl"))


def is_completed_episode(path: Path) -> bool:
    metadata_path = path / "metadata.json"
    if not metadata_path.exists():
        return True
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    return metadata.get("status") in {None, "completed"}


def control_value(record: dict[str, Any], key: str, *, requested: bool) -> float | None:
    control_key = "requested_control" if requested else "control"
    control = record.get(control_key)
    if not isinstance(control, dict):
        return None
    value = control.get(key)
    if value is None:
        return None
    return float(value)


def frame_number(record: dict[str, Any], fallback: int) -> int:
    value = record.get("frame")
    if isinstance(value, int):
        return value
    return fallback


def pct(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round((numerator / denominator) * 100.0, 3)


def add_top_record(
    records: list[dict[str, Any]],
    candidate: dict[str, Any],
    *,
    top_k: int,
) -> None:
    if top_k <= 0:
        return
    records.append(candidate)
    records.sort(key=lambda item: float(item["abs_delta"]), reverse=True)
    del records[top_k:]


def analyze_episode(
    episode_dir: Path,
    *,
    root: Path,
    args: argparse.Namespace,
    totals: dict[str, Any],
) -> None:
    source = str(episode_dir.relative_to(root)) if episode_dir != root else episode_dir.name
    episode_records = 0
    episode_requested = 0

    with (episode_dir / "manifest.jsonl").open("r", encoding="utf-8") as handle:
        for line_index, line in enumerate(handle):
            stripped = line.strip()
            if not stripped:
                continue
            episode_records += 1
            totals["records_scanned"] += 1
            try:
                record = json.loads(stripped)
            except json.JSONDecodeError:
                totals["decode_errors"] += 1
                continue

            values: dict[str, tuple[float, float]] = {}
            for key in CONTROL_KEYS:
                teacher = control_value(record, key, requested=False)
                model = control_value(record, key, requested=True)
                if teacher is None or model is None:
                    continue
                values[key] = (teacher, model)

            if len(values) != len(CONTROL_KEYS):
                continue

            episode_requested += 1
            totals["records_with_requested_control"] += 1
            frame = frame_number(record, line_index)
            for key, (teacher, model) in values.items():
                abs_delta = abs(teacher - model)
                totals["abs_delta_sum"][key] += abs_delta
                if abs_delta > totals["max_abs_delta"][key]["abs_delta"]:
                    totals["max_abs_delta"][key] = {
                        "source": source,
                        "frame": frame,
                        "teacher": teacher,
                        "model": model,
                        "abs_delta": abs_delta,
                    }
                add_top_record(
                    totals["worst_records"][key],
                    {
                        "source": source,
                        "frame": frame,
                        "teacher": teacher,
                        "model": model,
                        "abs_delta": abs_delta,
                    },
                    top_k=args.top_k,
                )

            teacher_brake = values["brake"][0] > args.brake_threshold
            model_brake = values["brake"][1] > args.brake_threshold
            teacher_throttle = values["throttle"][0] > args.throttle_threshold
            model_throttle = values["throttle"][1] > args.throttle_threshold
            steering_delta = abs(values["steering"][0] - values["steering"][1])

            totals["teacher_brake_frames"] += int(teacher_brake)
            totals["model_brake_frames"] += int(model_brake)
            totals["model_missing_teacher_brake_frames"] += int(teacher_brake and not model_brake)
            totals["model_extra_brake_frames"] += int(model_brake and not teacher_brake)
            totals["teacher_throttle_frames"] += int(teacher_throttle)
            totals["model_throttle_frames"] += int(model_throttle)
            totals["model_missing_teacher_throttle_frames"] += int(
                teacher_throttle and not model_throttle
            )
            totals["large_steering_delta_frames"] += int(
                steering_delta > args.steering_threshold
            )

    totals["episodes"].append(
        {
            "source": source,
            "records_scanned": episode_records,
            "records_with_requested_control": episode_requested,
        }
    )


def main() -> None:
    args = parse_args()
    episode_dirs = [
        path
        for path in discover_episode_dirs(args.dataset_root)
        if is_completed_episode(path)
    ]
    if not episode_dirs:
        raise SystemExit(f"No completed manifest datasets found under {args.dataset_root}")

    totals: dict[str, Any] = {
        "records_scanned": 0,
        "records_with_requested_control": 0,
        "decode_errors": 0,
        "abs_delta_sum": {key: 0.0 for key in CONTROL_KEYS},
        "max_abs_delta": {
            key: {"source": None, "frame": None, "teacher": 0.0, "model": 0.0, "abs_delta": 0.0}
            for key in CONTROL_KEYS
        },
        "worst_records": {key: [] for key in CONTROL_KEYS},
        "teacher_brake_frames": 0,
        "model_brake_frames": 0,
        "model_missing_teacher_brake_frames": 0,
        "model_extra_brake_frames": 0,
        "teacher_throttle_frames": 0,
        "model_throttle_frames": 0,
        "model_missing_teacher_throttle_frames": 0,
        "large_steering_delta_frames": 0,
        "episodes": [],
    }

    for episode_dir in episode_dirs:
        analyze_episode(episode_dir, root=args.dataset_root, args=args, totals=totals)

    compared = int(totals["records_with_requested_control"])
    summary = {
        "dataset_root": str(args.dataset_root),
        "datasets_scanned": len(episode_dirs),
        "records_scanned": totals["records_scanned"],
        "records_with_requested_control": compared,
        "decode_errors": totals["decode_errors"],
        "average_abs_delta": {
            key: round(totals["abs_delta_sum"][key] / max(compared, 1), 6)
            for key in CONTROL_KEYS
        },
        "max_abs_delta": totals["max_abs_delta"],
        "teacher_brake_frames": totals["teacher_brake_frames"],
        "model_brake_frames": totals["model_brake_frames"],
        "model_missing_teacher_brake_frames": totals["model_missing_teacher_brake_frames"],
        "model_extra_brake_frames": totals["model_extra_brake_frames"],
        "model_miss_when_teacher_braked_percent": pct(
            totals["model_missing_teacher_brake_frames"],
            totals["teacher_brake_frames"],
        ),
        "model_extra_brake_percent": pct(
            totals["model_extra_brake_frames"],
            compared - totals["teacher_brake_frames"],
        ),
        "teacher_throttle_frames": totals["teacher_throttle_frames"],
        "model_throttle_frames": totals["model_throttle_frames"],
        "model_missing_teacher_throttle_frames": totals[
            "model_missing_teacher_throttle_frames"
        ],
        "model_miss_when_teacher_throttled_percent": pct(
            totals["model_missing_teacher_throttle_frames"],
            totals["teacher_throttle_frames"],
        ),
        "large_steering_delta_frames": totals["large_steering_delta_frames"],
        "large_steering_delta_percent": pct(
            totals["large_steering_delta_frames"],
            compared,
        ),
        "worst_records": totals["worst_records"],
        "episodes": totals["episodes"],
    }

    text = json.dumps(summary, indent=2, sort_keys=True)
    if args.output_json is not None:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
