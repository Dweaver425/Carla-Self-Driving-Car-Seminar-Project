from __future__ import annotations

import argparse
import json
import tarfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class EpisodeSource:
    chunk_name: str
    vehicle_name: str
    path: Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Package collected chunk_*/vehicle_* CARLA episodes into one "
            "TAR-indexable dataset root. The output dataset keeps manifest and "
            "metadata files on disk, while images are stored in one uncompressed TAR."
        )
    )
    parser.add_argument(
        "--input-root",
        required=True,
        type=Path,
        help="Run folder containing chunk_* directories.",
    )
    parser.add_argument(
        "--output-root",
        required=True,
        type=Path,
        help="Folder where the packaged dataset root and image TAR will be written.",
    )
    parser.add_argument(
        "--dataset-name",
        required=True,
        help="Dataset folder name and top-level TAR prefix.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow replacing an existing packaged dataset or TAR.",
    )
    return parser.parse_args()


def discover_sources(input_root: Path) -> list[EpisodeSource]:
    sources: list[EpisodeSource] = []
    for chunk_dir in sorted(input_root.glob("chunk_*"), key=chunk_sort_key):
        if not chunk_dir.is_dir() or not (chunk_dir / "fleet_summary.json").exists():
            continue
        for vehicle_dir in sorted(chunk_dir.glob("vehicle_*")):
            if is_completed_episode(vehicle_dir):
                sources.append(
                    EpisodeSource(
                        chunk_name=chunk_dir.name,
                        vehicle_name=vehicle_dir.name,
                        path=vehicle_dir,
                    )
                )
    return sources


def chunk_sort_key(path: Path) -> tuple[int, str]:
    try:
        return int(path.name.split("_")[-1]), path.name
    except ValueError:
        return 10**9, path.name


def is_completed_episode(path: Path) -> bool:
    manifest_path = path / "manifest.jsonl"
    metadata_path = path / "metadata.json"
    if not manifest_path.exists() or not metadata_path.exists():
        return False
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    return metadata.get("status") == "completed"


def ensure_output_safe(dataset_root: Path, tar_path: Path, overwrite: bool) -> None:
    existing = [path for path in (dataset_root, tar_path) if path.exists()]
    if existing and not overwrite:
        names = ", ".join(str(path) for path in existing)
        raise FileExistsError(f"Output already exists ({names}). Use --overwrite to replace it.")


def package_dataset(
    *,
    input_root: Path,
    output_root: Path,
    dataset_name: str,
    overwrite: bool,
) -> dict[str, Any]:
    sources = discover_sources(input_root)
    if not sources:
        raise FileNotFoundError(f"No completed chunk_* vehicle episodes found under {input_root}")

    dataset_root = output_root / dataset_name
    tar_path = output_root / f"{dataset_name}_images.tar"
    ensure_output_safe(dataset_root, tar_path, overwrite)
    dataset_root.mkdir(parents=True, exist_ok=True)
    output_root.mkdir(parents=True, exist_ok=True)

    manifest_path = dataset_root / "manifest.jsonl"
    metadata_path = dataset_root / "metadata.json"
    tmp_manifest_path = manifest_path.with_suffix(".jsonl.tmp")
    tmp_tar_path = tar_path.with_suffix(".tar.tmp")

    total_records = 0
    skipped_records = 0
    source_names: list[str] = []
    created_at = datetime.now().astimezone().isoformat()

    try:
        with tmp_manifest_path.open("w", encoding="utf-8", newline="\n") as manifest_out:
            with tarfile.open(tmp_tar_path, mode="w") as tar:
                for source in sources:
                    source_name = f"{source.chunk_name}/{source.vehicle_name}"
                    source_names.append(source_name)
                    added_for_source = 0
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
                                arcname=f"{dataset_name}/{packaged_image_path}",
                                recursive=False,
                            )

                            record["image_path"] = packaged_image_path
                            record["source_chunk"] = source.chunk_name
                            record["source_vehicle"] = source.vehicle_name
                            manifest_out.write(json.dumps(record, sort_keys=True) + "\n")
                            total_records += 1
                            added_for_source += 1

                            if total_records % 50000 == 0:
                                print(
                                    {
                                        "event": "package_progress",
                                        "records": total_records,
                                        "source": source_name,
                                    },
                                    flush=True,
                                )

                    print(
                        {
                            "event": "episode_packaged",
                            "episode": source_name,
                            "records": added_for_source,
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
            },
            "controller": "combined_collected_chunks",
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

    return {
        "dataset_root": str(dataset_root),
        "dataset_name": dataset_name,
        "image_archive": str(tar_path),
        "records": total_records,
        "skipped_records": skipped_records,
        "source_episodes": len(sources),
    }


def main() -> None:
    args = parse_args()
    summary = package_dataset(
        input_root=args.input_root,
        output_root=args.output_root,
        dataset_name=args.dataset_name,
        overwrite=args.overwrite,
    )
    print(json.dumps(summary, indent=2, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
