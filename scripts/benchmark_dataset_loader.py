from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import torch
from torch.utils.data import DataLoader

from self_driving.data.dataset import DrivingDataset


def make_subset(dataset_root: Path, subset_root: Path, sample_count: int) -> int:
    if subset_root.exists():
        shutil.rmtree(subset_root)
    subset_root.mkdir(parents=True)

    manifest_path = dataset_root / "manifest.jsonl"
    index_path = dataset_root / "tar_image_index.jsonl"
    metadata_path = dataset_root / "tar_image_index_metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

    selected_manifest_lines: list[str] = []
    needed_images: set[str] = set()
    with manifest_path.open("r", encoding="utf-8") as manifest:
        for line in manifest:
            stripped = line.strip()
            if not stripped:
                continue
            record = json.loads(stripped)
            image_path = str(record["image_path"]).replace("\\", "/")
            selected_manifest_lines.append(json.dumps(record, sort_keys=True) + "\n")
            needed_images.add(image_path)
            if len(selected_manifest_lines) >= sample_count:
                break

    found_images: set[str] = set()
    with index_path.open("r", encoding="utf-8") as source, (
        subset_root / "tar_image_index.jsonl"
    ).open("w", encoding="utf-8", newline="\n") as target:
        for line in source:
            record = json.loads(line)
            image_path = str(record["image_path"]).replace("\\", "/")
            if image_path in needed_images:
                target.write(json.dumps(record, sort_keys=True) + "\n")
                found_images.add(image_path)
                if len(found_images) == len(needed_images):
                    break

    missing = needed_images - found_images
    if missing:
        raise FileNotFoundError(f"Missing {len(missing)} images from TAR index.")

    (subset_root / "manifest.jsonl").write_text(
        "".join(selected_manifest_lines),
        encoding="utf-8",
    )
    (subset_root / "tar_image_index_metadata.json").write_text(
        json.dumps(
            {
                "archive_path": metadata["archive_path"],
                "dataset_name": metadata["dataset_name"],
                "image_count": len(found_images),
                "index_path": str(subset_root / "tar_image_index.jsonl"),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return len(found_images)


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark TAR-indexed image loading.")
    parser.add_argument(
        "--dataset-root",
        type=Path,
        default=Path("data/raw/weekendCombined_v1/weekendCombined_v1"),
    )
    parser.add_argument("--samples", type=int, default=2048)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--num-workers", type=int, default=4)
    parser.add_argument("--batches", type=int, default=50)
    args = parser.parse_args()

    subset_root = args.dataset_root.parent / ".tar_loader_benchmark"
    try:
        available = make_subset(args.dataset_root, subset_root, args.samples)
        dataset = DrivingDataset(subset_root)
        loader = DataLoader(
            dataset,
            batch_size=args.batch_size,
            shuffle=True,
            num_workers=args.num_workers,
            persistent_workers=args.num_workers > 0,
            pin_memory=torch.cuda.is_available(),
        )

        measured_samples = 0
        started = time.perf_counter()
        for batch_index, (images, targets) in enumerate(loader, start=1):
            measured_samples += int(images.shape[0])
            _ = targets.shape
            if batch_index >= args.batches:
                break
        elapsed = max(0.001, time.perf_counter() - started)
        print(
            json.dumps(
                {
                    "available_subset_samples": available,
                    "batch_size": args.batch_size,
                    "batches": min(args.batches, batch_index),
                    "elapsed_seconds": round(elapsed, 3),
                    "image_shape": list(images.shape[1:]),
                    "measured_samples": measured_samples,
                    "num_workers": args.num_workers,
                    "samples_per_second": round(measured_samples / elapsed, 2),
                },
                sort_keys=True,
            )
        )
    finally:
        shutil.rmtree(subset_root, ignore_errors=True)


if __name__ == "__main__":
    main()
