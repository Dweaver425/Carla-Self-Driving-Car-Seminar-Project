from __future__ import annotations

import argparse
import io
import json
import tarfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class SegmentSummary:
    name: str
    path: Path
    records_added: int


class SplitWriter:
    """Write one logical stream to one file or a sequence of part files."""

    def __init__(self, output_path: Path, part_size_bytes: int | None = None) -> None:
        self.output_path = output_path
        self.part_size_bytes = part_size_bytes
        self._part_index = 0
        self._current_size = 0
        self._total_size = 0
        self._handle: io.BufferedWriter | None = None

    def write(self, data: bytes) -> int:
        if not data:
            return 0

        written = 0
        view = memoryview(data)
        while written < len(data):
            self._ensure_handle()
            assert self._handle is not None

            if self.part_size_bytes is None:
                chunk = view[written:]
            else:
                remaining = self.part_size_bytes - self._current_size
                if remaining <= 0:
                    self._open_next_part()
                    remaining = self.part_size_bytes
                chunk = view[written : written + remaining]

            chunk_size = self._handle.write(chunk)
            written += chunk_size
            self._current_size += chunk_size
            self._total_size += chunk_size

            if self.part_size_bytes is not None and self._current_size >= self.part_size_bytes:
                self._open_next_part()

        return written

    def tell(self) -> int:
        return self._total_size

    def flush(self) -> None:
        if self._handle is not None:
            self._handle.flush()

    def close(self) -> None:
        if self._handle is not None:
            self._handle.flush()
            self._handle.close()
            self._handle = None

    def _ensure_handle(self) -> None:
        if self._handle is None:
            self._open_next_part()

    def _open_next_part(self) -> None:
        if self._handle is not None:
            self._handle.flush()
            self._handle.close()

        self._part_index += 1
        self._current_size = 0
        path = self._current_part_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = path.open("wb")

    def _current_part_path(self) -> Path:
        if self.part_size_bytes is None:
            return self.output_path
        return self.output_path.with_name(f"{self.output_path.name}.part{self._part_index:03d}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build one combined uncompressed TAR dataset from CARLA segment_* folders. "
            "The script rewrites the manifest so the extracted archive becomes one dataset."
        )
    )
    parser.add_argument(
        "--input-root",
        required=True,
        type=Path,
        help="Folder that contains segment_* subdirectories.",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Output TAR path. Example: E:\\weekendCombined_v1.tar",
    )
    parser.add_argument(
        "--dataset-name",
        default="weekendCombined_v1",
        help="Top-level folder name inside the TAR archive.",
    )
    parser.add_argument(
        "--part-size-gb",
        type=float,
        default=None,
        help="Optional split size in GB. Use this for FAT32 flash drives.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow overwriting the output TAR path or TAR part files.",
    )
    return parser.parse_args()


def discover_segments(input_root: Path) -> list[Path]:
    segments = [path for path in input_root.glob("segment_*") if path.is_dir()]
    return sorted(segments, key=segment_sort_key)


def segment_sort_key(path: Path) -> tuple[int, str]:
    try:
        return int(path.name.split("_")[-1]), path.name
    except ValueError:
        return 10**9, path.name


def validate_segment(segment_dir: Path) -> bool:
    return (
        (segment_dir / "manifest.jsonl").exists()
        and (segment_dir / "metadata.json").exists()
        and (segment_dir / "images").exists()
    )


def add_bytes_as_file(tar: tarfile.TarFile, arcname: str, payload: bytes) -> None:
    info = tarfile.TarInfo(name=arcname)
    info.size = len(payload)
    info.mtime = datetime.now().timestamp()
    tar.addfile(info, io.BytesIO(payload))


def build_archive(
    input_root: Path,
    output_path: Path,
    dataset_name: str,
    part_size_bytes: int | None,
) -> dict[str, Any]:
    segments = discover_segments(input_root)
    if not segments:
        raise FileNotFoundError(f"No segment_* folders found under {input_root}")

    manifest_buffer = io.StringIO()
    source_segments: list[str] = []
    skipped_segments: list[str] = []
    segment_summaries: list[SegmentSummary] = []
    total_records = 0
    max_frame = 0

    writer = SplitWriter(output_path, part_size_bytes=part_size_bytes)
    try:
        with tarfile.open(fileobj=writer, mode="w|") as tar:
            for segment_dir in segments:
                segment_name = segment_dir.name
                if not validate_segment(segment_dir):
                    print(f"Skipping {segment_name}: missing manifest, metadata, or images.")
                    skipped_segments.append(segment_name)
                    continue

                records_added = 0
                manifest_path = segment_dir / "manifest.jsonl"
                with manifest_path.open("r", encoding="utf-8") as handle:
                    for line_number, line in enumerate(handle, start=1):
                        stripped = line.strip()
                        if not stripped:
                            continue

                        try:
                            record = json.loads(stripped)
                        except json.JSONDecodeError:
                            continue

                        image_path_value = record.get("image_path")
                        if not isinstance(image_path_value, str):
                            continue

                        source_image_path = segment_dir / image_path_value
                        if not source_image_path.exists():
                            continue

                        image_name = Path(image_path_value).name
                        new_image_name = f"{segment_name}_{image_name}"
                        tar_image_path = f"{dataset_name}/images/{new_image_name}"
                        tar.add(source_image_path, arcname=tar_image_path, recursive=False)

                        record["image_path"] = f"images/{new_image_name}"
                        record["source_segment"] = segment_name
                        manifest_buffer.write(json.dumps(record, sort_keys=True) + "\n")

                        frame_value = record.get("frame")
                        if isinstance(frame_value, int):
                            max_frame = max(max_frame, frame_value)

                        records_added += 1
                        total_records += 1

                        if total_records % 10000 == 0:
                            print(f"Added {total_records} records so far...")

                if records_added == 0:
                    print(f"Skipping {segment_name}: no valid records were found.")
                    skipped_segments.append(segment_name)
                    continue

                source_segments.append(segment_name)
                segment_summaries.append(
                    SegmentSummary(
                        name=segment_name,
                        path=segment_dir,
                        records_added=records_added,
                    )
                )
                print(f"Packed {segment_name}: {records_added} records.")

            if total_records == 0:
                raise ValueError("No valid records were added to the combined archive.")

            metadata = {
                "created_at": datetime.now().astimezone().isoformat(),
                "completed_at": datetime.now().astimezone().isoformat(),
                "config": {
                    "combined_from_root": str(input_root),
                    "source_segments": source_segments,
                    "skipped_segments": skipped_segments,
                    "archive_output": str(output_path),
                },
                "controller": "combined_segments",
                "frames_recorded": total_records,
                "last_frame": max_frame,
                "status": "completed",
            }

            add_bytes_as_file(
                tar,
                f"{dataset_name}/manifest.jsonl",
                manifest_buffer.getvalue().encode("utf-8"),
            )
            add_bytes_as_file(
                tar,
                f"{dataset_name}/metadata.json",
                json.dumps(metadata, indent=2, sort_keys=True).encode("utf-8"),
            )
    finally:
        writer.close()

    return {
        "archive_output": str(output_path),
        "dataset_name": dataset_name,
        "records": total_records,
        "source_segments": source_segments,
        "skipped_segments": skipped_segments,
        "parts": "multiple" if part_size_bytes is not None else "single",
        "segment_summaries": [
            {
                "name": summary.name,
                "path": str(summary.path),
                "records_added": summary.records_added,
            }
            for summary in segment_summaries
        ],
    }


def ensure_output_is_safe(output_path: Path, overwrite: bool, part_size_bytes: int | None) -> None:
    candidates = [output_path]
    if part_size_bytes is not None:
        candidates.extend(output_path.parent.glob(f"{output_path.name}.part*"))

    existing = [path for path in candidates if path.exists()]
    if existing and not overwrite:
        names = ", ".join(str(path) for path in existing[:5])
        raise FileExistsError(
            f"Output already exists ({names}). Use --overwrite if you want to replace it."
        )


def main() -> None:
    args = parse_args()
    part_size_bytes = None
    if args.part_size_gb is not None:
        part_size_bytes = int(args.part_size_gb * 1024 * 1024 * 1024)
        if part_size_bytes <= 0:
            raise ValueError("--part-size-gb must be greater than zero when provided.")

    ensure_output_is_safe(args.output, args.overwrite, part_size_bytes)
    summary = build_archive(
        input_root=args.input_root,
        output_path=args.output,
        dataset_name=args.dataset_name,
        part_size_bytes=part_size_bytes,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
