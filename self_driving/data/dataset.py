from __future__ import annotations

import json
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import AbstractSet
from typing import Any

import cv2
import numpy as np
import torch
from torch.utils.data import Dataset

from self_driving.modeling import TARGET_ORDER, image_to_tensor


@dataclass(frozen=True, slots=True)
class TarImageRef:
    offset: int
    size: int


@dataclass(frozen=True, slots=True)
class TarImageIndex:
    archive_path: Path
    entries: dict[str, TarImageRef]


@dataclass(frozen=True, slots=True)
class DrivingRecord:
    image_path: str
    target: tuple[float, float, float]
    image_shape: tuple[int, ...] | None


def load_tar_image_index(episode_dir: Path) -> TarImageIndex | None:
    metadata_path = episode_dir / "tar_image_index_metadata.json"
    index_path = episode_dir / "tar_image_index.jsonl"
    if not metadata_path.exists() or not index_path.exists():
        return None

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    archive_path = Path(metadata["archive_path"])
    if not archive_path.exists():
        raise FileNotFoundError(f"TAR archive from image index not found: {archive_path}")

    entries: dict[str, TarImageRef] = {}
    with index_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            record = json.loads(stripped)
            image_path = str(record["image_path"]).replace("\\", "/")
            entries[image_path] = TarImageRef(
                offset=int(record["offset"]),
                size=int(record["size"]),
            )

    if not entries:
        raise ValueError(f"TAR image index is empty: {index_path}")
    return TarImageIndex(archive_path=archive_path, entries=entries)


def load_manifest_records(
    episode_dir: Path,
    indexed_image_paths: AbstractSet[str] | None = None,
) -> list[DrivingRecord]:
    manifest_path = episode_dir / "manifest.jsonl"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Dataset manifest not found: {manifest_path}")

    records: list[DrivingRecord] = []
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

            normalized_image_path = image_path_value.replace("\\", "/")
            image_path = episode_dir / normalized_image_path
            image_is_indexed = (
                indexed_image_paths is not None
                and normalized_image_path in indexed_image_paths
            )
            if not image_path.exists() and not image_is_indexed:
                skipped_missing += 1
                continue

            control = record.get("control")
            if not isinstance(control, dict):
                skipped_invalid += 1
                continue

            try:
                target = tuple(float(control[name]) for name in TARGET_ORDER)
            except (KeyError, TypeError, ValueError):
                skipped_invalid += 1
                continue

            shape_value = record.get("image_shape")
            image_shape = tuple(shape_value) if isinstance(shape_value, list) else None
            records.append(
                DrivingRecord(
                    image_path=normalized_image_path,
                    target=target,  # type: ignore[arg-type]
                    image_shape=image_shape,
                )
            )

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
        self.tar_image_index = load_tar_image_index(self.episode_dir)
        indexed_paths = (
            self.tar_image_index.entries.keys()
            if self.tar_image_index is not None
            else None
        )
        self.records = load_manifest_records(self.episode_dir, indexed_paths)
        self.image_shape = self.records[0].image_shape
        self._tar_handle = None

    def __len__(self) -> int:
        return len(self.records)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, torch.Tensor]:
        record = self.records[index]
        image_bgr = self._load_image_bgr(record.image_path)

        image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        image_tensor = image_to_tensor(image_rgb)
        target_tensor = torch.tensor(record.target, dtype=torch.float32)
        return image_tensor, target_tensor

    def __getstate__(self) -> dict[str, Any]:
        state = self.__dict__.copy()
        state["_tar_handle"] = None
        return state

    def _load_image_bgr(self, image_path_value: str) -> np.ndarray:
        image_path_key = image_path_value.replace("\\", "/")
        image_path = self.episode_dir / image_path_key
        if image_path.exists():
            image_bgr = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
            if image_bgr is not None:
                return image_bgr

        if self.tar_image_index is None:
            raise FileNotFoundError(f"Failed to load image: {image_path}")

        image_ref = self.tar_image_index.entries.get(image_path_key)
        if image_ref is None:
            raise FileNotFoundError(
                f"Image is missing on disk and absent from TAR index: {image_path_key}"
            )

        handle = self._get_tar_handle()
        handle.seek(image_ref.offset)
        encoded = handle.read(image_ref.size)
        if len(encoded) != image_ref.size:
            raise EOFError(f"Short read from TAR for image: {image_path_key}")

        image_array = np.frombuffer(encoded, dtype=np.uint8)
        image_bgr = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
        if image_bgr is None:
            raise FileNotFoundError(f"Failed to decode image from TAR: {image_path_key}")
        return image_bgr

    def _get_tar_handle(self) -> Any:
        if self.tar_image_index is None:
            raise RuntimeError("TAR image index is not available.")
        if self._tar_handle is None:
            self._tar_handle = self.tar_image_index.archive_path.open("rb", buffering=1024 * 1024)
        return self._tar_handle
