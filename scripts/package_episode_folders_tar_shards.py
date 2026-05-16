from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from package_collected_chunks_tar import EpisodeSource, is_completed_episode
from package_collected_chunks_tar_shards import (
    CountedEpisode,
    build_index_for_shard,
    count_episode_records,
    package_shard,
    plan_shards,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Package selected flat CARLA episode folders into TAR-backed shards. "
            "Use this for older data/episodes/<episode_name> folders that are not "
            "inside chunk_*/vehicle_* fleet runs."
        )
    )
    parser.add_argument(
        "--episode-root",
        default=Path("data/episodes"),
        type=Path,
        help="Base folder used for relative episode names.",
    )
    parser.add_argument(
        "--episode-file",
        required=True,
        type=Path,
        help="Text file with one episode folder name or path per line.",
    )
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


def read_episode_file(path: Path) -> list[str]:
    episodes: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        value = line.strip()
        if not value or value.startswith("#"):
            continue
        episodes.append(value)
    return episodes


def resolve_episode_path(episode_root: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return episode_root / path


def safe_source_name(path: Path) -> str:
    return path.name.replace(" ", "_").replace("/", "_").replace("\\", "_")


def discover_sources(episode_root: Path, episode_file: Path) -> list[EpisodeSource]:
    sources: list[EpisodeSource] = []
    missing: list[str] = []
    incomplete: list[str] = []
    seen: set[Path] = set()

    for value in read_episode_file(episode_file):
        path = resolve_episode_path(episode_root, value)
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        if not path.exists():
            missing.append(str(path))
            continue
        if not is_completed_episode(path):
            incomplete.append(str(path))
            continue
        sources.append(
            EpisodeSource(
                chunk_name="episode",
                vehicle_name=safe_source_name(path),
                path=path,
            )
        )

    if missing:
        print({"event": "missing_episodes", "episodes": missing}, flush=True)
    if incomplete:
        print({"event": "incomplete_episodes_skipped", "episodes": incomplete}, flush=True)
    return sources


def package_selected_episodes(
    *,
    episode_root: Path,
    episode_file: Path,
    output_root: Path,
    dataset_name: str,
    min_images: int,
    target_images: int,
    overwrite: bool,
    skip_index: bool,
) -> dict[str, Any]:
    sources = discover_sources(episode_root, episode_file)
    counted = [
        CountedEpisode(source=source, records=count_episode_records(source))
        for source in sources
    ]
    counted = [episode for episode in counted if episode.records > 0]
    if not counted:
        raise FileNotFoundError(f"No completed episode folders found in {episode_file}")

    shards = plan_shards(
        counted,
        min_images=min_images,
        target_images=target_images,
    )
    output_root.mkdir(parents=True, exist_ok=True)
    dataset_file = output_root / f"{dataset_name}_datasets.txt"
    summary_path = output_root / f"{dataset_name}_shards_summary.json"

    print(
        {
            "event": "episode_shard_plan",
            "episodes": len(counted),
            "records": sum(episode.records for episode in counted),
            "shards": len(shards),
            "min_images": min_images,
            "target_images": target_images,
            "output_root": str(output_root),
        },
        flush=True,
    )

    summaries: list[dict[str, Any]] = []
    with dataset_file.open("w", encoding="utf-8", newline="\n") as dataset_out:
        for shard in shards:
            summary = package_shard(
                input_root=episode_root,
                output_root=output_root,
                dataset_name=dataset_name,
                shard=shard,
                overwrite=overwrite,
            )
            if not skip_index:
                build_index_for_shard(summary)
            dataset_out.write(str(summary["dataset_root"]) + "\n")
            summaries.append(summary)

    final_summary = {
        "dataset_file": str(dataset_file),
        "episode_file": str(episode_file),
        "episode_root": str(episode_root),
        "output_root": str(output_root),
        "records": sum(summary["records"] for summary in summaries),
        "shards": summaries,
        "source_episodes": len(counted),
    }
    summary_path.write_text(json.dumps(final_summary, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(final_summary, indent=2, sort_keys=True), flush=True)
    return final_summary


def main() -> None:
    args = parse_args()
    package_selected_episodes(
        episode_root=args.episode_root,
        episode_file=args.episode_file,
        output_root=args.output_root,
        dataset_name=args.dataset_name,
        min_images=args.min_images,
        target_images=args.target_images,
        overwrite=args.overwrite,
        skip_index=args.skip_index,
    )


if __name__ == "__main__":
    main()
