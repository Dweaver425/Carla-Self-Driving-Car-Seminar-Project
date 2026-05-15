from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tarfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from package_collected_chunks_tar import EpisodeSource, discover_sources


@dataclass(frozen=True, slots=True)
class CountedEpisode:
    source: EpisodeSource
    records: int


@dataclass(frozen=True, slots=True)
class ShardPlan:
    index: int
    episodes: list[CountedEpisode]
    records: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Package chunk_*/vehicle_* episodes into multiple TAR-backed dataset "
            "shards. Each shard targets roughly 50k-100k images by default."
        )
    )
    parser.add_argument("--input-root", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--dataset-name", required=True)
    parser.add_argument("--min-images", type=int, default=50_000)
    parser.add_argument("--target-images", type=int, default=100_000)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument(
        "--skip-index",
        action="store_true",
        help="Only build TARs/manifests. By default each shard is indexed for direct training.",
    )
    return parser.parse_args()


def count_episode_records(source: EpisodeSource) -> int:
    metadata_path = source.path / "metadata.json"
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        frames = int(metadata.get("frames_recorded", 0))
        if frames > 0:
            return frames
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        pass

    count = 0
    with (source.path / "manifest.jsonl").open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                count += 1
    return count


def plan_shards(
    episodes: list[CountedEpisode],
    *,
    min_images: int,
    target_images: int,
) -> list[ShardPlan]:
    if min_images <= 0:
        raise ValueError("--min-images must be greater than zero.")
    if target_images < min_images:
        raise ValueError("--target-images must be greater than or equal to --min-images.")

    shards: list[ShardPlan] = []
    current: list[CountedEpisode] = []
    current_records = 0

    for episode in episodes:
        if current and current_records >= min_images and current_records + episode.records > target_images:
            shards.append(
                ShardPlan(
                    index=len(shards) + 1,
                    episodes=current,
                    records=current_records,
                )
            )
            current = []
            current_records = 0

        current.append(episode)
        current_records += episode.records

        if current_records >= target_images:
            shards.append(
                ShardPlan(
                    index=len(shards) + 1,
                    episodes=current,
                    records=current_records,
                )
            )
            current = []
            current_records = 0

    if current:
        shards.append(
            ShardPlan(
                index=len(shards) + 1,
                episodes=current,
                records=current_records,
            )
        )
    return shards


def ensure_shard_output_safe(dataset_root: Path, tar_path: Path, overwrite: bool) -> None:
    existing = [path for path in (dataset_root, tar_path) if path.exists()]
    if existing and not overwrite:
        names = ", ".join(str(path) for path in existing)
        raise FileExistsError(f"Output already exists ({names}). Use --overwrite to replace it.")


def package_shard(
    *,
    input_root: Path,
    output_root: Path,
    dataset_name: str,
    shard: ShardPlan,
    overwrite: bool,
) -> dict[str, Any]:
    shard_name = f"{dataset_name}_shard_{shard.index:03d}"
    dataset_root = output_root / shard_name
    tar_path = output_root / f"{shard_name}_images.tar"
    ensure_shard_output_safe(dataset_root, tar_path, overwrite)
    dataset_root.mkdir(parents=True, exist_ok=True)
    output_root.mkdir(parents=True, exist_ok=True)

    manifest_path = dataset_root / "manifest.jsonl"
    metadata_path = dataset_root / "metadata.json"
    tmp_manifest_path = manifest_path.with_suffix(".jsonl.tmp")
    tmp_tar_path = tar_path.with_suffix(".tar.tmp")
    source_names: list[str] = []
    total_records = 0
    skipped_records = 0
    created_at = datetime.now().astimezone().isoformat()

    try:
        with tmp_manifest_path.open("w", encoding="utf-8", newline="\n") as manifest_out:
            with tarfile.open(tmp_tar_path, mode="w") as tar:
                for episode in shard.episodes:
                    source = episode.source
                    source_name = f"{source.chunk_name}/{source.vehicle_name}"
                    source_names.append(source_name)
                    with (source.path / "manifest.jsonl").open("r", encoding="utf-8") as manifest_in:
                        for line in manifest_in:
                            stripped = line.strip()
                            if not stripped:
                                continue
                            try:
                                record = json.loads(stripped)
                            except json.JSONDecodeError:
                                skipped_records += 1
                                continue

                            image_path_value = record.get("image_path")
                            if not isinstance(image_path_value, str):
                                skipped_records += 1
                                continue

                            source_image_path = source.path / image_path_value
                            if not source_image_path.exists():
                                skipped_records += 1
                                continue

                            image_name = source_image_path.name
                            packaged_image_name = (
                                f"{source.chunk_name}_{source.vehicle_name}_{image_name}"
                            )
                            packaged_image_path = f"images/{packaged_image_name}"
                            tar.add(
                                source_image_path,
                                arcname=f"{shard_name}/{packaged_image_path}",
                                recursive=False,
                            )

                            record["image_path"] = packaged_image_path
                            record["source_chunk"] = source.chunk_name
                            record["source_vehicle"] = source.vehicle_name
                            record["source_shard"] = shard_name
                            manifest_out.write(json.dumps(record, sort_keys=True) + "\n")
                            total_records += 1

                            if total_records % 50_000 == 0:
                                print(
                                    {
                                        "event": "shard_package_progress",
                                        "records": total_records,
                                        "shard": shard_name,
                                    },
                                    flush=True,
                                )

        metadata = {
            "created_at": created_at,
            "completed_at": datetime.now().astimezone().isoformat(),
            "config": {
                "combined_from_root": str(input_root),
                "source_episodes": source_names,
                "image_archive": str(tar_path.resolve()),
                "shard_index": shard.index,
                "shard_name": shard_name,
            },
            "controller": "combined_collected_chunks_tar_shard",
            "frames_recorded": total_records,
            "last_frame": total_records,
            "status": "completed",
        }
        metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")
        tmp_manifest_path.replace(manifest_path)
        tmp_tar_path.replace(tar_path)
    except Exception:
        for path in (tmp_manifest_path, tmp_tar_path):
            if path.exists():
                path.unlink()
        raise

    summary = {
        "dataset_root": str(dataset_root),
        "dataset_name": shard_name,
        "image_archive": str(tar_path),
        "records": total_records,
        "planned_records": shard.records,
        "skipped_records": skipped_records,
        "source_episodes": len(shard.episodes),
    }
    print({"event": "shard_packaged", **summary}, flush=True)
    return summary


def build_index_for_shard(summary: dict[str, Any]) -> None:
    script_path = Path(__file__).with_name("build_tar_image_index.py")
    command = [
        sys.executable,
        str(script_path),
        "--tar",
        str(summary["image_archive"]),
        "--dataset-root",
        str(summary["dataset_root"]),
        "--dataset-name",
        str(summary["dataset_name"]),
        "--overwrite",
    ]
    subprocess.run(command, check=True)


def main() -> None:
    args = parse_args()
    sources = discover_sources(args.input_root)
    counted = [
        CountedEpisode(source=source, records=count_episode_records(source))
        for source in sources
    ]
    counted = [episode for episode in counted if episode.records > 0]
    if not counted:
        raise FileNotFoundError(f"No completed chunk_* vehicle episodes found under {args.input_root}")

    shards = plan_shards(
        counted,
        min_images=args.min_images,
        target_images=args.target_images,
    )
    args.output_root.mkdir(parents=True, exist_ok=True)
    dataset_file = args.output_root / f"{args.dataset_name}_datasets.txt"
    summary_path = args.output_root / f"{args.dataset_name}_shards_summary.json"

    print(
        {
            "event": "shard_plan",
            "episodes": len(counted),
            "records": sum(episode.records for episode in counted),
            "shards": len(shards),
            "min_images": args.min_images,
            "target_images": args.target_images,
            "output_root": str(args.output_root),
        },
        flush=True,
    )

    summaries: list[dict[str, Any]] = []
    with dataset_file.open("w", encoding="utf-8", newline="\n") as dataset_out:
        for shard in shards:
            summary = package_shard(
                input_root=args.input_root,
                output_root=args.output_root,
                dataset_name=args.dataset_name,
                shard=shard,
                overwrite=args.overwrite,
            )
            if not args.skip_index:
                build_index_for_shard(summary)
            dataset_out.write(str(summary["dataset_root"]) + "\n")
            summaries.append(summary)

    final_summary = {
        "dataset_file": str(dataset_file),
        "input_root": str(args.input_root),
        "output_root": str(args.output_root),
        "records": sum(summary["records"] for summary in summaries),
        "shards": summaries,
        "source_episodes": len(counted),
    }
    summary_path.write_text(json.dumps(final_summary, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(final_summary, indent=2, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
