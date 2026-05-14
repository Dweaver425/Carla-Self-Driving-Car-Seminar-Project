from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from statistics import mean

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cv2
import numpy as np
import torch

from self_driving.modeling import TARGET_ORDER, image_to_tensor, load_driving_model


def load_sample_records(dataset_root: Path, samples: int) -> list[dict]:
    metadata_path = dataset_root / "tar_image_index_metadata.json"
    total = samples
    if metadata_path.exists():
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        total = int(metadata.get("image_count", samples))

    stride = max(1, total // samples)
    records: list[dict] = []
    with (dataset_root / "manifest.jsonl").open("r", encoding="utf-8") as manifest:
        for line_number, line in enumerate(manifest):
            if line_number % stride != 0:
                continue
            stripped = line.strip()
            if not stripped:
                continue
            record = json.loads(stripped)
            image_path = str(record["image_path"]).replace("\\", "/")
            control = record["control"]
            records.append(
                {
                    "image_path": image_path,
                    "target": [float(control[name]) for name in TARGET_ORDER],
                }
            )
            if len(records) >= samples:
                break
    return records


def load_needed_index(dataset_root: Path, image_paths: set[str]) -> tuple[Path, dict[str, tuple[int, int]]]:
    metadata = json.loads((dataset_root / "tar_image_index_metadata.json").read_text(encoding="utf-8"))
    archive_path = Path(metadata["archive_path"])
    entries: dict[str, tuple[int, int]] = {}
    with (dataset_root / "tar_image_index.jsonl").open("r", encoding="utf-8") as index_file:
        for line in index_file:
            record = json.loads(line)
            image_path = str(record["image_path"]).replace("\\", "/")
            if image_path in image_paths:
                entries[image_path] = (int(record["offset"]), int(record["size"]))
                if len(entries) == len(image_paths):
                    break
    return archive_path, entries


def load_image(dataset_root: Path, archive, index: dict[str, tuple[int, int]], image_path: str) -> np.ndarray:
    disk_path = dataset_root / image_path
    if disk_path.exists():
        image_bgr = cv2.imread(str(disk_path), cv2.IMREAD_COLOR)
        if image_bgr is not None:
            return cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)

    offset, size = index[image_path]
    archive.seek(offset)
    encoded = archive.read(size)
    image_bgr = cv2.imdecode(np.frombuffer(encoded, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image_bgr is None:
        raise RuntimeError(f"Failed to decode {image_path}")
    return cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)


def summarize(values: list[float]) -> dict[str, float]:
    array = np.asarray(values, dtype=np.float64)
    return {
        "mean": round(float(array.mean()), 6),
        "std": round(float(array.std()), 6),
        "min": round(float(array.min()), 6),
        "max": round(float(array.max()), 6),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare checkpoint predictions to dataset labels.")
    parser.add_argument("--checkpoint", default="models/carla_weekend_tar_index_cuda.pt")
    parser.add_argument(
        "--dataset-root",
        default="data/raw/carla_weekend_combined/carla_weekend_combined",
        type=Path,
    )
    parser.add_argument("--samples", type=int, default=1024)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--device", default="cuda")
    args = parser.parse_args()

    records = load_sample_records(args.dataset_root, args.samples)
    archive_path, index = load_needed_index(
        args.dataset_root,
        {record["image_path"] for record in records},
    )
    model, device, checkpoint = load_driving_model(args.checkpoint, device=args.device)
    model.eval()

    predictions: list[list[float]] = []
    targets = [record["target"] for record in records]
    with archive_path.open("rb", buffering=1024 * 1024) as archive:
        for start in range(0, len(records), args.batch_size):
            batch_records = records[start : start + args.batch_size]
            images = [
                image_to_tensor(load_image(args.dataset_root, archive, index, record["image_path"]))
                for record in batch_records
            ]
            tensor = torch.stack(images).to(device)
            with torch.no_grad():
                output = model(tensor).detach().cpu().numpy()
            predictions.extend(output.tolist())

    target_by_name = dict(zip(TARGET_ORDER, zip(*targets), strict=True))
    prediction_by_name = dict(zip(TARGET_ORDER, zip(*predictions), strict=True))
    result = {
        "checkpoint": args.checkpoint,
        "completed_epoch": checkpoint["training"].get("completed_epoch"),
        "samples": len(records),
        "target": {name: summarize(list(values)) for name, values in target_by_name.items()},
        "prediction_raw": {
            name: summarize(list(values)) for name, values in prediction_by_name.items()
        },
        "prediction_clamped": {
            "throttle": summarize([min(1.0, max(0.0, row[0])) for row in predictions]),
            "steering": summarize([min(1.0, max(-1.0, row[1])) for row in predictions]),
            "brake": summarize([min(1.0, max(0.0, row[2])) for row in predictions]),
        },
        "fractions": {
            "pred_throttle_below_0_05": round(
                mean(1.0 if min(1.0, max(0.0, row[0])) < 0.05 else 0.0 for row in predictions),
                6,
            ),
            "pred_brake_above_0_05": round(
                mean(1.0 if min(1.0, max(0.0, row[2])) > 0.05 else 0.0 for row in predictions),
                6,
            ),
            "target_throttle_below_0_05": round(
                mean(1.0 if row[0] < 0.05 else 0.0 for row in targets),
                6,
            ),
            "target_brake_above_0_05": round(
                mean(1.0 if row[2] > 0.05 else 0.0 for row in targets),
                6,
            ),
        },
    }
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
