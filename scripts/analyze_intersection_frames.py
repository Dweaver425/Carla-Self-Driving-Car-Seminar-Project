from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


CONTROL_KEYS = ("throttle", "steering", "brake")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compare how many recorded frames CARLA teacher and model runs spend "
            "inside junctions/intersections."
        )
    )
    parser.add_argument(
        "--teacher-root",
        type=Path,
        default=None,
        help="CARLA autopilot run root or episode folder.",
    )
    parser.add_argument(
        "--model-root",
        type=Path,
        default=None,
        help="Model-only run root or episode folder.",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=None,
        help="Optional path to save the JSON summary.",
    )
    parser.add_argument(
        "--write-teacher-dataset",
        type=Path,
        default=None,
        help="Optional dataset-file path containing teacher episodes with junction frames.",
    )
    parser.add_argument(
        "--min-junction-frames",
        type=int,
        default=1,
        help="Minimum teacher junction frames required before writing an episode to the dataset file.",
    )
    parser.add_argument("--top-k", type=int, default=10)
    return parser.parse_args()


def discover_episode_dirs(root: Path) -> list[Path]:
    if (root / "manifest.jsonl").exists():
        return [root]
    return sorted(path.parent for path in root.rglob("manifest.jsonl"))


def metadata_for_episode(path: Path) -> dict[str, Any]:
    metadata_path = path / "metadata.json"
    if not metadata_path.exists():
        return {}
    try:
        return json.loads(metadata_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"status": "invalid_metadata"}


def is_completed_episode(path: Path) -> bool:
    metadata = metadata_for_episode(path)
    return metadata.get("status") in {None, "completed"}


def has_manifest_records(path: Path) -> bool:
    manifest_path = path / "manifest.jsonl"
    return manifest_path.exists() and manifest_path.stat().st_size > 0


def frame_number(record: dict[str, Any], fallback: int) -> int:
    value = record.get("frame")
    return int(value) if isinstance(value, int) else fallback


def is_junction_record(record: dict[str, Any]) -> bool:
    lane_details = record.get("lane_details")
    return isinstance(lane_details, dict) and bool(lane_details.get("is_junction"))


def float_value(record: dict[str, Any], key: str) -> float | None:
    value = record.get(key)
    if isinstance(value, int | float):
        return float(value)
    return None


def control_value(record: dict[str, Any], key: str, *, requested: bool) -> float | None:
    control_key = "requested_control" if requested else "control"
    control = record.get(control_key)
    if not isinstance(control, dict):
        return None
    value = control.get(key)
    if isinstance(value, int | float):
        return float(value)
    return None


def pct(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round((numerator / denominator) * 100.0, 3)


def rounded_ratio(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round(numerator / denominator, 3)


def finalize_junction_event(
    *,
    source: str,
    records: list[dict[str, Any]],
    start_frame: int,
    end_frame: int,
) -> dict[str, Any]:
    offsets = [
        abs(value)
        for record in records
        if (value := float_value(record, "lane_offset_m")) is not None
    ]
    headings = [
        abs(value)
        for record in records
        if (value := float_value(record, "heading_error_deg")) is not None
    ]
    return {
        "source": source,
        "start_frame": start_frame,
        "end_frame": end_frame,
        "frames": len(records),
        "avg_abs_lane_offset_m": round(sum(offsets) / max(len(offsets), 1), 6),
        "avg_abs_heading_error_deg": round(sum(headings) / max(len(headings), 1), 6),
        "max_abs_lane_offset_m": round(max(offsets, default=0.0), 6),
        "max_abs_heading_error_deg": round(max(headings, default=0.0), 6),
    }


def add_top_event(events: list[dict[str, Any]], event: dict[str, Any], *, top_k: int) -> None:
    if top_k <= 0:
        return
    events.append(event)
    events.sort(key=lambda item: int(item["frames"]), reverse=True)
    del events[top_k:]


def summarize_episode(
    episode_dir: Path,
    *,
    root: Path,
    top_k: int,
) -> dict[str, Any]:
    source = str(episode_dir.relative_to(root)) if episode_dir != root else episode_dir.name
    metadata = metadata_for_episode(episode_dir)
    controller = metadata.get("controller")
    records = 0
    junction_frames = 0
    lane_offset_sum = 0.0
    lane_offset_count = 0
    heading_sum = 0.0
    heading_count = 0
    junction_lane_offset_sum = 0.0
    junction_lane_offset_count = 0
    junction_heading_sum = 0.0
    junction_heading_count = 0
    max_abs_lane_offset = 0.0
    max_abs_heading = 0.0
    junction_max_abs_lane_offset = 0.0
    junction_max_abs_heading = 0.0
    requested_records = 0
    delta_sum = {key: 0.0 for key in CONTROL_KEYS}
    junction_delta_sum = {key: 0.0 for key in CONTROL_KEYS}
    junction_requested_records = 0
    top_events: list[dict[str, Any]] = []
    active_junction_records: list[dict[str, Any]] = []
    active_start_frame: int | None = None
    active_end_frame: int | None = None

    with (episode_dir / "manifest.jsonl").open("r", encoding="utf-8") as handle:
        for line_index, line in enumerate(handle):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                record = json.loads(stripped)
            except json.JSONDecodeError:
                continue

            frame = frame_number(record, line_index)
            records += 1
            is_junction = is_junction_record(record)
            lane_offset = float_value(record, "lane_offset_m")
            if lane_offset is not None:
                abs_offset = abs(lane_offset)
                lane_offset_sum += abs_offset
                lane_offset_count += 1
                max_abs_lane_offset = max(max_abs_lane_offset, abs_offset)
                if is_junction:
                    junction_lane_offset_sum += abs_offset
                    junction_lane_offset_count += 1
                    junction_max_abs_lane_offset = max(junction_max_abs_lane_offset, abs_offset)
            heading = float_value(record, "heading_error_deg")
            if heading is not None:
                abs_heading = abs(heading)
                heading_sum += abs_heading
                heading_count += 1
                max_abs_heading = max(max_abs_heading, abs_heading)
                if is_junction:
                    junction_heading_sum += abs_heading
                    junction_heading_count += 1
                    junction_max_abs_heading = max(junction_max_abs_heading, abs_heading)

            values: dict[str, tuple[float, float]] = {}
            for key in CONTROL_KEYS:
                teacher = control_value(record, key, requested=False)
                model = control_value(record, key, requested=True)
                if teacher is not None and model is not None:
                    values[key] = (teacher, model)
            if len(values) == len(CONTROL_KEYS):
                requested_records += 1
                if is_junction:
                    junction_requested_records += 1
                for key, (teacher, model) in values.items():
                    delta = abs(teacher - model)
                    delta_sum[key] += delta
                    if is_junction:
                        junction_delta_sum[key] += delta

            if is_junction:
                junction_frames += 1
                if active_start_frame is None:
                    active_start_frame = frame
                active_end_frame = frame
                active_junction_records.append(record)
            elif active_junction_records:
                add_top_event(
                    top_events,
                    finalize_junction_event(
                        source=source,
                        records=active_junction_records,
                        start_frame=int(active_start_frame),
                        end_frame=int(active_end_frame),
                    ),
                    top_k=top_k,
                )
                active_junction_records = []
                active_start_frame = None
                active_end_frame = None

    if active_junction_records:
        add_top_event(
            top_events,
            finalize_junction_event(
                source=source,
                records=active_junction_records,
                start_frame=int(active_start_frame),
                end_frame=int(active_end_frame),
            ),
            top_k=top_k,
        )

    return {
        "source": source,
        "path": str(episode_dir),
        "controller": controller,
        "records_scanned": records,
        "junction_frames": junction_frames,
        "junction_percent": pct(junction_frames, records),
        "avg_abs_lane_offset_m": round(lane_offset_sum / max(lane_offset_count, 1), 6),
        "avg_abs_heading_error_deg": round(heading_sum / max(heading_count, 1), 6),
        "max_abs_lane_offset_m": round(max_abs_lane_offset, 6),
        "max_abs_heading_error_deg": round(max_abs_heading, 6),
        "junction_avg_abs_lane_offset_m": round(
            junction_lane_offset_sum / max(junction_lane_offset_count, 1), 6
        ),
        "junction_avg_abs_heading_error_deg": round(
            junction_heading_sum / max(junction_heading_count, 1), 6
        ),
        "junction_max_abs_lane_offset_m": round(junction_max_abs_lane_offset, 6),
        "junction_max_abs_heading_error_deg": round(junction_max_abs_heading, 6),
        "records_with_requested_control": requested_records,
        "junction_records_with_requested_control": junction_requested_records,
        "average_abs_control_delta": {
            key: round(delta_sum[key] / max(requested_records, 1), 6)
            for key in CONTROL_KEYS
        },
        "junction_average_abs_control_delta": {
            key: round(junction_delta_sum[key] / max(junction_requested_records, 1), 6)
            for key in CONTROL_KEYS
        },
        "top_junction_events": top_events,
    }


def summarize_root(root: Path, *, top_k: int) -> dict[str, Any]:
    candidate_episode_dirs = [
        path
        for path in discover_episode_dirs(root)
        if is_completed_episode(path)
        and has_manifest_records(path)
    ]
    if not candidate_episode_dirs:
        raise SystemExit(f"No completed non-empty manifest datasets found under {root}")

    episodes = [
        item
        for path in candidate_episode_dirs
        if int((item := summarize_episode(path, root=root, top_k=top_k))["records_scanned"]) > 0
    ]
    if not episodes:
        raise SystemExit(f"No valid records found in completed manifest datasets under {root}")
    records = sum(int(item["records_scanned"]) for item in episodes)
    junction_frames = sum(int(item["junction_frames"]) for item in episodes)
    requested_records = sum(int(item["records_with_requested_control"]) for item in episodes)
    junction_requested_records = sum(
        int(item["junction_records_with_requested_control"]) for item in episodes
    )
    train_episode_paths = [
        item["path"]
        for item in episodes
        if int(item["junction_frames"]) > 0
    ]

    def weighted_average(key: str, weight_key: str) -> float:
        numerator = sum(float(item[key]) * int(item[weight_key]) for item in episodes)
        denominator = sum(int(item[weight_key]) for item in episodes)
        return round(numerator / max(denominator, 1), 6)

    delta_summary = {
        key: round(
            sum(
                float(item["average_abs_control_delta"][key])
                * int(item["records_with_requested_control"])
                for item in episodes
            )
            / max(requested_records, 1),
            6,
        )
        for key in CONTROL_KEYS
    }
    junction_delta_summary = {
        key: round(
            sum(
                float(item["junction_average_abs_control_delta"][key])
                * int(item["junction_records_with_requested_control"])
                for item in episodes
            )
            / max(junction_requested_records, 1),
            6,
        )
        for key in CONTROL_KEYS
    }
    top_events: list[dict[str, Any]] = []
    for item in episodes:
        for event in item["top_junction_events"]:
            add_top_event(top_events, event, top_k=top_k)

    return {
        "root": str(root),
        "datasets_scanned": len(episodes),
        "records_scanned": records,
        "junction_frames": junction_frames,
        "junction_percent": pct(junction_frames, records),
        "avg_abs_lane_offset_m": weighted_average("avg_abs_lane_offset_m", "records_scanned"),
        "avg_abs_heading_error_deg": weighted_average(
            "avg_abs_heading_error_deg",
            "records_scanned",
        ),
        "junction_avg_abs_lane_offset_m": weighted_average(
            "junction_avg_abs_lane_offset_m",
            "junction_frames",
        ),
        "junction_avg_abs_heading_error_deg": weighted_average(
            "junction_avg_abs_heading_error_deg",
            "junction_frames",
        ),
        "max_abs_lane_offset_m": round(
            max(float(item["max_abs_lane_offset_m"]) for item in episodes),
            6,
        ),
        "max_abs_heading_error_deg": round(
            max(float(item["max_abs_heading_error_deg"]) for item in episodes),
            6,
        ),
        "junction_max_abs_lane_offset_m": round(
            max(float(item["junction_max_abs_lane_offset_m"]) for item in episodes),
            6,
        ),
        "junction_max_abs_heading_error_deg": round(
            max(float(item["junction_max_abs_heading_error_deg"]) for item in episodes),
            6,
        ),
        "records_with_requested_control": requested_records,
        "junction_records_with_requested_control": junction_requested_records,
        "average_abs_control_delta": delta_summary,
        "junction_average_abs_control_delta": junction_delta_summary,
        "train_episode_paths": train_episode_paths,
        "top_junction_events": top_events,
        "episodes": episodes,
    }


def build_comparison(
    teacher_summary: dict[str, Any] | None,
    model_summary: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if teacher_summary is None or model_summary is None:
        return None
    teacher_junction = int(teacher_summary["junction_frames"])
    model_junction = int(model_summary["junction_frames"])
    return {
        "teacher_junction_frames": teacher_junction,
        "model_junction_frames": model_junction,
        "model_minus_teacher_junction_frames": model_junction - teacher_junction,
        "model_to_teacher_junction_frame_ratio": rounded_ratio(model_junction, teacher_junction),
        "teacher_junction_percent": teacher_summary["junction_percent"],
        "model_junction_percent": model_summary["junction_percent"],
        "model_minus_teacher_junction_percent": round(
            float(model_summary["junction_percent"])
            - float(teacher_summary["junction_percent"]),
            3,
        ),
        "teacher_junction_avg_abs_lane_offset_m": teacher_summary[
            "junction_avg_abs_lane_offset_m"
        ],
        "model_junction_avg_abs_lane_offset_m": model_summary[
            "junction_avg_abs_lane_offset_m"
        ],
        "teacher_junction_max_abs_lane_offset_m": teacher_summary[
            "junction_max_abs_lane_offset_m"
        ],
        "model_junction_max_abs_lane_offset_m": model_summary[
            "junction_max_abs_lane_offset_m"
        ],
    }


def main() -> None:
    args = parse_args()
    if args.teacher_root is None and args.model_root is None:
        raise SystemExit("Provide --teacher-root, --model-root, or both.")

    teacher_summary = (
        summarize_root(args.teacher_root, top_k=args.top_k)
        if args.teacher_root is not None
        else None
    )
    model_summary = (
        summarize_root(args.model_root, top_k=args.top_k)
        if args.model_root is not None
        else None
    )

    if args.write_teacher_dataset is not None:
        if teacher_summary is None:
            raise SystemExit("--write-teacher-dataset requires --teacher-root.")
        train_paths = [
            item["path"]
            for item in teacher_summary["episodes"]
            if int(item["junction_frames"]) >= args.min_junction_frames
        ]
        if not train_paths:
            raise SystemExit(
                "No teacher episodes had at least "
                f"{args.min_junction_frames} junction frame(s); not writing an empty "
                "training dataset file."
            )
        args.write_teacher_dataset.parent.mkdir(parents=True, exist_ok=True)
        args.write_teacher_dataset.write_text(
            "".join(f"{path}\n" for path in train_paths),
            encoding="utf-8",
        )

    summary = {
        "teacher": teacher_summary,
        "model": model_summary,
        "comparison": build_comparison(teacher_summary, model_summary),
        "teacher_dataset_file": (
            str(args.write_teacher_dataset)
            if args.write_teacher_dataset is not None
            else None
        ),
    }
    text = json.dumps(summary, indent=2, sort_keys=True)
    if args.output_json is not None:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
