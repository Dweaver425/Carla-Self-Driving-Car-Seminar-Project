from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean
from typing import Any


@dataclass(slots=True)
class StopSignEvent:
    source: str
    stop_id: int
    start_frame: int
    end_frame: int
    frames: int
    teacher_brake_frames: int
    teacher_stopped_frames: int
    model_brake_frames: int
    model_missing_brake_frames: int
    first_forward_m: float
    min_forward_m: float
    last_forward_m: float
    avg_teacher_brake: float
    avg_model_brake: float | None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Analyze CARLA-teacher stop-sign frames and compare them with a shadow "
            "model's requested_control brake response."
        )
    )
    parser.add_argument(
        "--dataset-root",
        required=True,
        type=Path,
        help="A run root, chunk folder, vehicle episode folder, or TAR-indexed dataset root.",
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=None,
        help="Optional CSV path for per-stop-sign event details.",
    )
    parser.add_argument("--brake-threshold", type=float, default=0.05)
    parser.add_argument("--stopped-speed", type=float, default=0.25)
    parser.add_argument("--event-gap-frames", type=int, default=10)
    return parser.parse_args()


def discover_episode_dirs(root: Path) -> list[Path]:
    if (root / "manifest.jsonl").exists():
        return [root]

    candidates: list[Path] = []
    for manifest_path in root.rglob("manifest.jsonl"):
        episode_dir = manifest_path.parent
        metadata_path = episode_dir / "metadata.json"
        if metadata_path.exists():
            candidates.append(episode_dir)
    return sorted(candidates)


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


def speed_mps(record: dict[str, Any]) -> float:
    state = record.get("state")
    if not isinstance(state, dict):
        return 0.0
    return float(state.get("speed_mps", 0.0))


def stop_sign_details(record: dict[str, Any]) -> dict[str, Any] | None:
    details = record.get("traffic_rule_details")
    if not isinstance(details, dict):
        return None
    stop_sign = details.get("stop_sign")
    if not isinstance(stop_sign, dict):
        return None
    return stop_sign


def frame_number(record: dict[str, Any], fallback: int) -> int:
    value = record.get("frame")
    if isinstance(value, int):
        return value
    return fallback


def finalize_event(
    *,
    source: str,
    stop_id: int,
    records: list[dict[str, Any]],
    brake_threshold: float,
    stopped_speed: float,
) -> StopSignEvent:
    frames = [frame_number(record, index) for index, record in enumerate(records)]
    teacher_brakes = [
        control_value(record, "brake", requested=False) or 0.0
        for record in records
    ]
    model_brakes = [
        control_value(record, "brake", requested=True)
        for record in records
    ]
    forward_distances = [
        float(stop_sign_details(record).get("forward_distance_m", 999.0))  # type: ignore[union-attr]
        for record in records
    ]
    teacher_brake_frames = sum(value > brake_threshold for value in teacher_brakes)
    teacher_stopped_frames = sum(speed_mps(record) <= stopped_speed for record in records)
    model_brake_values = [value for value in model_brakes if value is not None]
    model_brake_frames = sum(
        value is not None and value > brake_threshold
        for value in model_brakes
    )
    model_missing_brake_frames = sum(
        teacher > brake_threshold
        and (model is None or model <= brake_threshold)
        for teacher, model in zip(teacher_brakes, model_brakes, strict=True)
    )
    return StopSignEvent(
        source=source,
        stop_id=stop_id,
        start_frame=min(frames),
        end_frame=max(frames),
        frames=len(records),
        teacher_brake_frames=teacher_brake_frames,
        teacher_stopped_frames=teacher_stopped_frames,
        model_brake_frames=model_brake_frames,
        model_missing_brake_frames=model_missing_brake_frames,
        first_forward_m=forward_distances[0],
        min_forward_m=min(forward_distances),
        last_forward_m=forward_distances[-1],
        avg_teacher_brake=mean(teacher_brakes),
        avg_model_brake=mean(model_brake_values) if model_brake_values else None,
    )


def analyze_episode(
    episode_dir: Path,
    *,
    root: Path,
    brake_threshold: float,
    stopped_speed: float,
    event_gap_frames: int,
) -> tuple[int, list[StopSignEvent]]:
    source = str(episode_dir.relative_to(root)) if episode_dir != root else episode_dir.name
    events: list[StopSignEvent] = []
    records_scanned = 0
    active_stop_id: int | None = None
    active_records: list[dict[str, Any]] = []
    last_frame: int | None = None

    with (episode_dir / "manifest.jsonl").open("r", encoding="utf-8") as handle:
        for line_index, line in enumerate(handle):
            stripped = line.strip()
            if not stripped:
                continue
            records_scanned += 1
            try:
                record = json.loads(stripped)
            except json.JSONDecodeError:
                continue

            stop_sign = stop_sign_details(record)
            current_frame = frame_number(record, line_index)
            current_stop_id = int(stop_sign.get("id", -1)) if stop_sign is not None else None
            gap = (
                last_frame is not None
                and current_frame - last_frame > event_gap_frames
            )
            should_close = (
                active_records
                and (
                    current_stop_id is None
                    or current_stop_id != active_stop_id
                    or gap
                )
            )
            if should_close:
                events.append(
                    finalize_event(
                        source=source,
                        stop_id=int(active_stop_id if active_stop_id is not None else -1),
                        records=active_records,
                        brake_threshold=brake_threshold,
                        stopped_speed=stopped_speed,
                    )
                )
                active_records = []
                active_stop_id = None

            if stop_sign is not None:
                active_stop_id = current_stop_id
                active_records.append(record)
                last_frame = current_frame

    if active_records:
        events.append(
            finalize_event(
                source=source,
                stop_id=int(active_stop_id if active_stop_id is not None else -1),
                records=active_records,
                brake_threshold=brake_threshold,
                stopped_speed=stopped_speed,
            )
        )

    return records_scanned, events


def write_csv(path: Path, events: list[StopSignEvent]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "source",
                "stop_id",
                "start_frame",
                "end_frame",
                "frames",
                "teacher_brake_frames",
                "teacher_stopped_frames",
                "model_brake_frames",
                "model_missing_brake_frames",
                "first_forward_m",
                "min_forward_m",
                "last_forward_m",
                "avg_teacher_brake",
                "avg_model_brake",
            ],
        )
        writer.writeheader()
        for event in events:
            writer.writerow(asdict(event))


def pct(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round((numerator / denominator) * 100.0, 3)


def main() -> None:
    args = parse_args()
    episode_dirs = [
        path
        for path in discover_episode_dirs(args.dataset_root)
        if is_completed_episode(path)
    ]
    if not episode_dirs:
        raise SystemExit(f"No completed manifest datasets found under {args.dataset_root}")

    all_events: list[StopSignEvent] = []
    records_scanned = 0
    for episode_dir in episode_dirs:
        count, events = analyze_episode(
            episode_dir,
            root=args.dataset_root,
            brake_threshold=args.brake_threshold,
            stopped_speed=args.stopped_speed,
            event_gap_frames=args.event_gap_frames,
        )
        records_scanned += count
        all_events.extend(events)

    total_stop_frames = sum(event.frames for event in all_events)
    teacher_brake_frames = sum(event.teacher_brake_frames for event in all_events)
    teacher_stopped_frames = sum(event.teacher_stopped_frames for event in all_events)
    model_brake_frames = sum(event.model_brake_frames for event in all_events)
    model_missing_brake_frames = sum(event.model_missing_brake_frames for event in all_events)
    events_with_model_brake = sum(event.model_brake_frames > 0 for event in all_events)
    events_with_teacher_stop = sum(event.teacher_stopped_frames > 0 for event in all_events)

    summary = {
        "dataset_root": str(args.dataset_root),
        "datasets_scanned": len(episode_dirs),
        "records_scanned": records_scanned,
        "stop_sign_events": len(all_events),
        "stop_sign_frames": total_stop_frames,
        "avg_stop_sign_frames_per_event": round(
            mean(event.frames for event in all_events), 3
        )
        if all_events
        else 0.0,
        "events_with_teacher_full_stop": events_with_teacher_stop,
        "events_with_model_brake": events_with_model_brake,
        "teacher_brake_frames": teacher_brake_frames,
        "teacher_stopped_frames": teacher_stopped_frames,
        "model_brake_frames": model_brake_frames,
        "model_missing_teacher_brake_frames": model_missing_brake_frames,
        "model_brake_coverage_percent": pct(model_brake_frames, total_stop_frames),
        "model_miss_when_teacher_braked_percent": pct(
            model_missing_brake_frames,
            teacher_brake_frames,
        ),
        "shortest_events": [
            asdict(event)
            for event in sorted(all_events, key=lambda item: item.frames)[:10]
        ],
        "worst_model_miss_events": [
            asdict(event)
            for event in sorted(
                all_events,
                key=lambda item: item.model_missing_brake_frames,
                reverse=True,
            )[:10]
        ],
    }

    if args.output_csv is not None:
        write_csv(args.output_csv, all_events)
        summary["output_csv"] = str(args.output_csv)

    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
