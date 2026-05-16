from __future__ import annotations

import argparse
import json
import math
import os
import re
import time
from pathlib import Path, PurePosixPath


BLOCK_SIZE = 512
SEGMENT_RE = re.compile(r"/segment_(\d+)_")


def parse_octal(raw: bytes) -> int:
    value = raw.split(b"\0", 1)[0].strip()
    if not value:
        return 0
    return int(value, 8)


def decode_tar_text(raw: bytes) -> str:
    return raw.split(b"\0", 1)[0].decode("utf-8", "surrogateescape")


def parse_pax_headers(data: bytes) -> dict[str, str]:
    headers: dict[str, str] = {}
    pos = 0
    while pos < len(data):
        space = data.find(b" ", pos)
        if space == -1:
            break
        try:
            record_len = int(data[pos:space])
        except ValueError:
            break
        record = data[space + 1 : pos + record_len]
        if record.endswith(b"\n"):
            record = record[:-1]
        key, sep, value = record.partition(b"=")
        if sep:
            headers[key.decode("utf-8", "surrogateescape")] = value.decode(
                "utf-8", "surrogateescape"
            )
        pos += record_len
    return headers


def padded_size(size: int) -> int:
    return int(math.ceil(size / BLOCK_SIZE) * BLOCK_SIZE)


def read_header(file_obj, pending_name: str | None, pending_pax: dict[str, str] | None):
    offset = file_obj.tell()
    block = file_obj.read(BLOCK_SIZE)
    if not block:
        return None, None, None
    if len(block) != BLOCK_SIZE:
        raise EOFError(f"short TAR header at byte offset {offset}")
    if block == b"\0" * BLOCK_SIZE:
        return {"end": True, "offset": offset}, None, None

    name = decode_tar_text(block[0:100])
    prefix = decode_tar_text(block[345:500])
    path = f"{prefix}/{name}" if prefix else name
    if pending_name:
        path = pending_name
        pending_name = None
    if pending_pax:
        path = pending_pax.get("path", path)
        pending_pax = None

    return (
        {
            "offset": offset,
            "path": path,
            "size": parse_octal(block[124:136]),
            "typeflag": block[156:157],
        },
        pending_name,
        pending_pax,
    )


def segment_for_path(path: str) -> int | None:
    match = SEGMENT_RE.search(path)
    if not match:
        return None
    return int(match.group(1))


def is_safe_member_path(member_path: str) -> bool:
    path = PurePosixPath(member_path)
    if path.is_absolute():
        return False
    return all(part not in ("", ".", "..") for part in path.parts)


def destination_for(destination_root: Path, member_path: str) -> Path:
    if not is_safe_member_path(member_path):
        raise ValueError(f"unsafe TAR member path: {member_path}")
    return destination_root.joinpath(*PurePosixPath(member_path).parts)


def get_free_gb(path: Path) -> float:
    usage = os.statvfs(path) if hasattr(os, "statvfs") else None
    if usage:
        return round((usage.f_bavail * usage.f_frsize) / (1024**3), 1)

    import ctypes

    free_bytes = ctypes.c_ulonglong(0)
    ctypes.windll.kernel32.GetDiskFreeSpaceExW(
        ctypes.c_wchar_p(str(path.resolve())),
        None,
        None,
        ctypes.pointer(free_bytes),
    )
    return round(free_bytes.value / (1024**3), 1)


def write_state(
    state_path: Path,
    *,
    running: bool,
    pid: int,
    tar_path: Path,
    archive_offset: int,
    start_offset: int,
    files_written: int,
    files_skipped_existing: int,
    bytes_written: int,
    started_at: float,
    last_archive_offset: int,
    last_bytes_written: int,
    last_state_at: float,
    current_member: str,
    current_segment: int | None,
    target_segments: list[int],
    exit_code: int | None,
) -> None:
    now = time.time()
    elapsed = max(0.001, now - started_at)
    interval = max(0.001, now - last_state_at)
    archive_delta = max(0, archive_offset - last_archive_offset)
    write_delta = max(0, bytes_written - last_bytes_written)
    tar_size = tar_path.stat().st_size
    state = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "pid": pid,
        "running": running,
        "tarPath": str(tar_path),
        "archiveOffset": archive_offset,
        "archiveScannedGB": round(archive_offset / (1024**3), 2),
        "archivePercent": round((archive_offset / tar_size) * 100.0, 2),
        "startOffset": start_offset,
        "elapsedMinutes": round(elapsed / 60.0, 1),
        "intervalArchiveMBps": round((archive_delta / (1024**2)) / interval, 2),
        "averageArchiveMBps": round(((archive_offset - start_offset) / (1024**2)) / elapsed, 2),
        "intervalWriteMBps": round((write_delta / (1024**2)) / interval, 2),
        "averageWriteMBps": round((bytes_written / (1024**2)) / elapsed, 2),
        "filesWritten": files_written,
        "filesSkippedExisting": files_skipped_existing,
        "bytesWritten": bytes_written,
        "writtenGB": round(bytes_written / (1024**3), 2),
        "freeGB": get_free_gb(state_path.parent),
        "currentSegment": current_segment,
        "currentMember": current_member,
        "targetSegments": target_segments,
        "exitCode": exit_code,
    }
    tmp_path = state_path.with_suffix(state_path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    tmp_path.replace(state_path)


def copy_member(file_obj, destination: Path, size: int, buffer_size: int) -> int:
    destination.parent.mkdir(parents=True, exist_ok=True)
    tmp_destination = destination.with_name(destination.name + ".part")
    remaining = size
    written = 0
    with tmp_destination.open("wb") as out:
        while remaining > 0:
            chunk = file_obj.read(min(buffer_size, remaining))
            if not chunk:
                raise EOFError(f"unexpected EOF while extracting {destination}")
            out.write(chunk)
            remaining -= len(chunk)
            written += len(chunk)
    tmp_destination.replace(destination)
    return written


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fast segment-targeted extractor for an uncompressed CARLA TAR."
    )
    parser.add_argument("--tar", required=True, type=Path)
    parser.add_argument("--dest", required=True, type=Path)
    parser.add_argument("--dataset", default="weekendCombined_v1")
    parser.add_argument("--start-segment", type=int, default=31)
    parser.add_argument("--end-segment", type=int, default=52)
    parser.add_argument("--skip-segment", action="append", type=int, default=[38])
    parser.add_argument("--state", type=Path, default=None)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--skip-existing", action="store_true")
    parser.add_argument("--state-seconds", type=float, default=30.0)
    parser.add_argument("--buffer-mb", type=int, default=4)
    args = parser.parse_args()

    tar_path = args.tar.resolve()
    destination_root = args.dest.resolve()
    state_path = args.state or destination_root / "fast_extract_state.json"
    target_segments = [
        segment
        for segment in range(args.start_segment, args.end_segment + 1)
        if segment not in set(args.skip_segment)
    ]
    prefixes = tuple(
        f"{args.dataset}/images/segment_{segment}_" for segment in target_segments
    )

    destination_root.mkdir(parents=True, exist_ok=True)
    state_path.parent.mkdir(parents=True, exist_ok=True)

    start_offset = 0
    files_written = 0
    files_skipped_existing = 0
    bytes_written = 0
    if args.resume and state_path.exists():
        previous = json.loads(state_path.read_text(encoding="utf-8"))
        start_offset = int(previous.get("archiveOffset", 0))
        files_written = int(previous.get("filesWritten", 0))
        files_skipped_existing = int(previous.get("filesSkippedExisting", 0))
        bytes_written = int(previous.get("bytesWritten", 0))

    started_at = time.time()
    last_state_at = started_at
    last_archive_offset = start_offset
    last_bytes_written = bytes_written
    current_member = ""
    current_segment: int | None = None
    pending_name: str | None = None
    pending_pax: dict[str, str] | None = None
    archive_offset = start_offset
    exit_code: int | None = None

    print("Fast TAR segment extraction", flush=True)
    print(f"Archive: {tar_path}", flush=True)
    print(f"Destination: {destination_root}", flush=True)
    print(f"State: {state_path}", flush=True)
    print(f"Segments: {', '.join(str(segment) for segment in target_segments)}", flush=True)
    print(f"Start offset: {start_offset}", flush=True)

    try:
        with tar_path.open("rb", buffering=1024 * 1024) as file_obj:
            file_obj.seek(start_offset)
            while True:
                header, pending_name, pending_pax = read_header(
                    file_obj, pending_name, pending_pax
                )
                if header is None or header.get("end"):
                    archive_offset = file_obj.tell()
                    exit_code = 0
                    break

                current_member = header["path"]
                current_segment = segment_for_path(current_member)
                size = header["size"]
                typeflag = header["typeflag"]
                data_offset = file_obj.tell()
                next_offset = data_offset + padded_size(size)

                if typeflag == b"L":
                    pending_name = file_obj.read(size).split(b"\0", 1)[0].decode(
                        "utf-8", "surrogateescape"
                    )
                    file_obj.seek(next_offset)
                    archive_offset = next_offset
                    continue

                if typeflag in (b"x", b"g"):
                    pax_data = file_obj.read(size)
                    if typeflag == b"x":
                        pending_pax = parse_pax_headers(pax_data)
                    file_obj.seek(next_offset)
                    archive_offset = next_offset
                    continue

                should_extract = current_member.startswith(prefixes)
                is_regular_file = typeflag in (b"0", b"\0", b"")
                if should_extract and is_regular_file:
                    destination = destination_for(destination_root, current_member)
                    if args.skip_existing and destination.exists():
                        files_skipped_existing += 1
                        file_obj.seek(next_offset)
                    else:
                        bytes_written += copy_member(
                            file_obj,
                            destination,
                            size,
                            args.buffer_mb * 1024 * 1024,
                        )
                        files_written += 1
                        padding = padded_size(size) - size
                        if padding:
                            file_obj.seek(padding, os.SEEK_CUR)
                else:
                    file_obj.seek(next_offset)

                archive_offset = next_offset
                now = time.time()
                if now - last_state_at >= args.state_seconds:
                    write_state(
                        state_path,
                        running=True,
                        pid=os.getpid(),
                        tar_path=tar_path,
                        archive_offset=archive_offset,
                        start_offset=start_offset,
                        files_written=files_written,
                        files_skipped_existing=files_skipped_existing,
                        bytes_written=bytes_written,
                        started_at=started_at,
                        last_archive_offset=last_archive_offset,
                        last_bytes_written=last_bytes_written,
                        last_state_at=last_state_at,
                        current_member=current_member,
                        current_segment=current_segment,
                        target_segments=target_segments,
                        exit_code=None,
                    )
                    last_state_at = now
                    last_archive_offset = archive_offset
                    last_bytes_written = bytes_written

        write_state(
            state_path,
            running=False,
            pid=os.getpid(),
            tar_path=tar_path,
            archive_offset=archive_offset,
            start_offset=start_offset,
            files_written=files_written,
            files_skipped_existing=files_skipped_existing,
            bytes_written=bytes_written,
            started_at=started_at,
            last_archive_offset=last_archive_offset,
            last_bytes_written=last_bytes_written,
            last_state_at=last_state_at,
            current_member=current_member,
            current_segment=current_segment,
            target_segments=target_segments,
            exit_code=exit_code,
        )
        print(f"Finished with exit code {exit_code}", flush=True)
        return exit_code or 0
    except KeyboardInterrupt:
        exit_code = 130
        print("Interrupted", flush=True)
        return exit_code
    finally:
        if exit_code is None:
            write_state(
                state_path,
                running=False,
                pid=os.getpid(),
                tar_path=tar_path,
                archive_offset=archive_offset,
                start_offset=start_offset,
                files_written=files_written,
                files_skipped_existing=files_skipped_existing,
                bytes_written=bytes_written,
                started_at=started_at,
                last_archive_offset=last_archive_offset,
                last_bytes_written=last_bytes_written,
                last_state_at=last_state_at,
                current_member=current_member,
                current_segment=current_segment,
                target_segments=target_segments,
                exit_code=1,
            )


if __name__ == "__main__":
    raise SystemExit(main())
