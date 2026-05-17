from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build a text file containing completed CARLA episode folders with "
            "non-empty manifests and positive recorded frame counts."
        )
    )
    parser.add_argument(
        "--episode-root",
        type=Path,
        default=Path("data/episodes"),
        help="Root folder to scan recursively for episode manifests.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Text file to write one relative episode path per line.",
    )
    parser.add_argument(
        "--summary-output",
        type=Path,
        default=None,
        help="Optional JSON summary path.",
    )
    return parser.parse_args()


def metadata_for_episode(path: Path) -> dict[str, Any] | None:
    metadata_path = path / "metadata.json"
    if not metadata_path.exists():
        return None
    try:
        return json.loads(metadata_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def build_episode_file(
    *,
    episode_root: Path,
    output: Path,
    summary_output: Path | None,
) -> dict[str, Any]:
    episode_root = episode_root.resolve()
    rows: list[dict[str, Any]] = []
    skipped = {
        "bad_metadata": 0,
        "empty_manifest": 0,
        "missing_metadata": 0,
        "not_completed": 0,
        "zero_frames": 0,
    }

    for manifest_path in sorted(episode_root.rglob("manifest.jsonl")):
        episode_dir = manifest_path.parent
        if manifest_path.stat().st_size <= 0:
            skipped["empty_manifest"] += 1
            continue

        metadata = metadata_for_episode(episode_dir)
        if metadata is None:
            if (episode_dir / "metadata.json").exists():
                skipped["bad_metadata"] += 1
            else:
                skipped["missing_metadata"] += 1
            continue
        if metadata.get("status") != "completed":
            skipped["not_completed"] += 1
            continue

        try:
            frames = int(metadata.get("frames_recorded") or 0)
        except (TypeError, ValueError):
            frames = 0
        if frames <= 0:
            skipped["zero_frames"] += 1
            continue

        rows.append(
            {
                "controller": metadata.get("controller"),
                "episode": episode_dir.relative_to(episode_root).as_posix(),
                "frames": frames,
            }
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        "".join(f"{row['episode']}\n" for row in rows),
        encoding="utf-8",
        newline="\n",
    )

    summary = {
        "episode_file": str(output),
        "episode_root": str(episode_root),
        "episodes": len(rows),
        "frames_from_metadata": sum(int(row["frames"]) for row in rows),
        "skipped": skipped,
        "sources": rows,
    }
    if summary_output is not None:
        summary_output.parent.mkdir(parents=True, exist_ok=True)
        summary_output.write_text(
            json.dumps(summary, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    return summary


def main() -> None:
    args = parse_args()
    summary = build_episode_file(
        episode_root=args.episode_root,
        output=args.output,
        summary_output=args.summary_output,
    )
    print(
        json.dumps(
            {
                "episode_file": summary["episode_file"],
                "episodes": summary["episodes"],
                "frames_from_metadata": summary["frames_from_metadata"],
                "skipped": summary["skipped"],
            },
            indent=2,
            sort_keys=True,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
