from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime
from pathlib import Path

from extract_tar_segments_fast import (
    padded_size,
    parse_pax_headers,
    read_header,
    segment_for_path,
)


def write_state(
    state_path: Path,
    *,
    running: bool,
    pid: int,
    archive_offset: int,
    archive_size: int,
    image_count: int,
    started_at: float,
    last_offset: int,
    last_state_at: float,
    current_member: str,
    current_segment: int | None,
    exit_code: int | None,
) -> None:
    now = time.time()
    elapsed = max(0.001, now - started_at)
    interval = max(0.001, now - last_state_at)
    offset_delta = max(0, archive_offset - last_offset)
    state = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "pid": pid,
        "running": running,
        "archiveOffset": archive_offset,
        "archiveScannedGB": round(archive_offset / (1024**3), 2),
        "archivePercent": round((archive_offset / archive_size) * 100.0, 2),
        "elapsedMinutes": round(elapsed / 60.0, 1),
        "intervalArchiveMBps": round((offset_delta / (1024**2)) / interval, 2),
        "averageArchiveMBps": round((archive_offset / (1024**2)) / elapsed, 2),
        "imagesIndexed": image_count,
        "currentSegment": current_segment,
        "currentMember": current_member,
        "exitCode": exit_code,
    }
    tmp_path = state_path.with_suffix(state_path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    tmp_path.replace(state_path)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a random-access image index for an uncompressed CARLA TAR."
    )
    parser.add_argument("--tar", required=True, type=Path)
    parser.add_argument("--dataset-root", required=True, type=Path)
    parser.add_argument("--dataset-name", default="carla_weekend_combined")
    parser.add_argument("--index-name", default="tar_image_index.jsonl")
    parser.add_argument("--metadata-name", default="tar_image_index_metadata.json")
    parser.add_argument("--state-name", default="tar_image_index_state.json")
    parser.add_argument("--state-seconds", type=float, default=15.0)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    tar_path = args.tar.resolve()
    dataset_root = args.dataset_root.resolve()
    index_path = dataset_root / args.index_name
    metadata_path = dataset_root / args.metadata_name
    state_path = dataset_root / args.state_name
    tmp_index_path = index_path.with_suffix(index_path.suffix + ".tmp")

    if index_path.exists() and not args.overwrite:
        raise FileExistsError(f"Index already exists: {index_path}. Use --overwrite.")

    dataset_root.mkdir(parents=True, exist_ok=True)
    image_prefix = f"{args.dataset_name}/images/"
    archive_size = tar_path.stat().st_size
    started_at = time.time()
    last_state_at = started_at
    last_offset = 0
    archive_offset = 0
    image_count = 0
    current_member = ""
    current_segment: int | None = None
    pending_name: str | None = None
    pending_pax: dict[str, str] | None = None
    exit_code: int | None = None

    print("Building TAR image index", flush=True)
    print(f"Archive: {tar_path}", flush=True)
    print(f"Dataset root: {dataset_root}", flush=True)
    print(f"Index: {index_path}", flush=True)

    try:
        with tar_path.open("rb", buffering=1024 * 1024) as tar_file, tmp_index_path.open(
            "w", encoding="utf-8", newline="\n"
        ) as index_file:
            while True:
                header, pending_name, pending_pax = read_header(
                    tar_file, pending_name, pending_pax
                )
                if header is None or header.get("end"):
                    archive_offset = tar_file.tell()
                    exit_code = 0
                    break

                current_member = header["path"]
                current_segment = segment_for_path(current_member)
                size = header["size"]
                typeflag = header["typeflag"]
                data_offset = tar_file.tell()
                next_offset = data_offset + padded_size(size)

                if typeflag == b"L":
                    pending_name = tar_file.read(size).split(b"\0", 1)[0].decode(
                        "utf-8", "surrogateescape"
                    )
                    tar_file.seek(next_offset)
                    archive_offset = next_offset
                    continue

                if typeflag in (b"x", b"g"):
                    pax_data = tar_file.read(size)
                    if typeflag == b"x":
                        pending_pax = parse_pax_headers(pax_data)
                    tar_file.seek(next_offset)
                    archive_offset = next_offset
                    continue

                is_regular_file = typeflag in (b"0", b"\0", b"")
                if (
                    is_regular_file
                    and current_member.startswith(image_prefix)
                    and current_member.lower().endswith(".png")
                ):
                    image_path = current_member[len(args.dataset_name) + 1 :]
                    index_file.write(
                        json.dumps(
                            {
                                "image_path": image_path,
                                "tar_path": current_member,
                                "offset": data_offset,
                                "size": size,
                            },
                            sort_keys=True,
                        )
                        + "\n"
                    )
                    image_count += 1

                tar_file.seek(next_offset)
                archive_offset = next_offset
                now = time.time()
                if now - last_state_at >= args.state_seconds:
                    write_state(
                        state_path,
                        running=True,
                        pid=os.getpid(),
                        archive_offset=archive_offset,
                        archive_size=archive_size,
                        image_count=image_count,
                        started_at=started_at,
                        last_offset=last_offset,
                        last_state_at=last_state_at,
                        current_member=current_member,
                        current_segment=current_segment,
                        exit_code=None,
                    )
                    last_state_at = now
                    last_offset = archive_offset

        tmp_index_path.replace(index_path)
        metadata = {
            "archive_path": str(tar_path),
            "created_at": datetime.now().astimezone().isoformat(),
            "dataset_name": args.dataset_name,
            "image_count": image_count,
            "index_path": str(index_path),
        }
        metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        write_state(
            state_path,
            running=False,
            pid=os.getpid(),
            archive_offset=archive_offset,
            archive_size=archive_size,
            image_count=image_count,
            started_at=started_at,
            last_offset=last_offset,
            last_state_at=last_state_at,
            current_member=current_member,
            current_segment=current_segment,
            exit_code=exit_code,
        )
        print(json.dumps(metadata, indent=2), flush=True)
        return exit_code or 0
    finally:
        if exit_code is None:
            write_state(
                state_path,
                running=False,
                pid=os.getpid(),
                archive_offset=archive_offset,
                archive_size=archive_size,
                image_count=image_count,
                started_at=started_at,
                last_offset=last_offset,
                last_state_at=last_state_at,
                current_member=current_member,
                current_segment=current_segment,
                exit_code=1,
            )


if __name__ == "__main__":
    raise SystemExit(main())
