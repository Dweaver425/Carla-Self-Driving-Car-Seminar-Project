from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from self_driving.data.dataset import DrivingDataset


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke-test TAR-indexed dataset loading.")
    parser.add_argument(
        "--dataset-root",
        type=Path,
        default=Path("data/raw/weekendCombined_v1/weekendCombined_v1"),
    )
    args = parser.parse_args()

    dataset_root = args.dataset_root
    index_path = dataset_root / "tar_image_index.jsonl"
    metadata_path = dataset_root / "tar_image_index_metadata.json"
    if not index_path.exists() or not metadata_path.exists():
        raise FileNotFoundError("TAR index files are missing.")

    first_index_line = index_path.read_text(encoding="utf-8").splitlines()[0]
    first_index_record = json.loads(first_index_line)
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

    smoke_root = dataset_root.parent / ".tar_index_smoke_test"
    if smoke_root.exists():
        shutil.rmtree(smoke_root)
    smoke_root.mkdir(parents=True)

    try:
        manifest_record = {
            "control": {"brake": 0.0, "steering": 0.0, "throttle": 0.0},
            "image_path": first_index_record["image_path"],
            "image_shape": [90, 160, 3],
        }
        (smoke_root / "manifest.jsonl").write_text(
            json.dumps(manifest_record) + "\n",
            encoding="utf-8",
        )
        (smoke_root / "tar_image_index.jsonl").write_text(
            json.dumps(first_index_record, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (smoke_root / "tar_image_index_metadata.json").write_text(
            json.dumps(
                {
                    "archive_path": metadata["archive_path"],
                    "dataset_name": metadata["dataset_name"],
                    "image_count": 1,
                    "index_path": str(smoke_root / "tar_image_index.jsonl"),
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        dataset = DrivingDataset(smoke_root)
        image, target = dataset[0]
        print(
            json.dumps(
                {
                    "samples": len(dataset),
                    "image_shape": list(image.shape),
                    "target": [float(value) for value in target.tolist()],
                    "source_image": first_index_record["image_path"],
                },
                sort_keys=True,
            )
        )
    finally:
        shutil.rmtree(smoke_root, ignore_errors=True)


if __name__ == "__main__":
    main()
