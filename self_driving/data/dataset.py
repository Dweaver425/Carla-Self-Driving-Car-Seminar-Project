from __future__ import annotations

import json
import warnings
from pathlib import Path
from typing import Any

import cv2
import torch
from torch.utils.data import Dataset

from self_driving.modeling import TARGET_ORDER, image_to_tensor


def load_manifest_records(episode_dir: Path) -> list[dict[str, Any]]:
    manifest_path = episode_dir / "manifest.jsonl"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Dataset manifest not found: {manifest_path}")

    records: list[dict[str, Any]] = []
    skipped_invalid = 0
    skipped_missing = 0
    with manifest_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue

            try:
                record = json.loads(stripped)
            except json.JSONDecodeError:
                skipped_invalid += 1
                continue

            image_path_value = record.get("image_path")
            if not isinstance(image_path_value, str):
                skipped_invalid += 1
                continue

            image_path = episode_dir / image_path_value
            if not image_path.exists():
                skipped_missing += 1
                continue

            records.append(record)

    if not records:
        raise ValueError(f"Dataset manifest is empty: {manifest_path}")
    if skipped_invalid or skipped_missing:
        warnings.warn(
            "Skipped incomplete dataset records while loading "
            f"{episode_dir} (invalid={skipped_invalid}, missing_images={skipped_missing}).",
            stacklevel=2,
        )
    return records


class DrivingDataset(Dataset[tuple[torch.Tensor, torch.Tensor]]):
    def __init__(self, episode_dir: str | Path) -> None:
        self.episode_dir = Path(episode_dir)
        self.records = load_manifest_records(self.episode_dir)
        shape = self.records[0].get("image_shape")
        self.image_shape = tuple(shape) if shape else None

    def __len__(self) -> int:
        return len(self.records)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, torch.Tensor]:
        record = self.records[index]
        image_path = self.episode_dir / record["image_path"]
        image_bgr = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
        if image_bgr is None:
            raise FileNotFoundError(f"Failed to load image: {image_path}")

        image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        image_tensor = image_to_tensor(image_rgb)
        target_tensor = torch.tensor(
            [float(record["control"][name]) for name in TARGET_ORDER],
            dtype=torch.float32,
        )
        return image_tensor, target_tensor
