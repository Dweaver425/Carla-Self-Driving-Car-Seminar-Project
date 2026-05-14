from __future__ import annotations

import json
import os
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2

from self_driving.config import SimulationConfig
from self_driving.networking.messages import FleetMessage
from self_driving.types import ControlCommand, DrivingObservation


class EpisodeRecorder:
    _PROGRESS_WRITE_INTERVAL = 100

    def __init__(
        self,
        output_dir: str | Path,
        config: SimulationConfig,
        controller_name: str,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.images_dir = self.output_dir / "images"
        self.manifest_path = self.output_dir / "manifest.jsonl"
        self.metadata_path = self.output_dir / "metadata.json"
        self._controller_name = controller_name
        self._config = config
        self._created_at = datetime.now().astimezone().isoformat()
        self._frames_recorded = 0
        self._last_frame = 0
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.images_dir.mkdir(parents=True, exist_ok=True)
        self._manifest_handle = self.manifest_path.open("w", encoding="utf-8")

        self._write_metadata(status="recording")

    def record(
        self,
        observation: DrivingObservation,
        command: ControlCommand,
        message: FleetMessage,
        alerts: list[dict[str, Any]] | None = None,
        requested_control: ControlCommand | None = None,
    ) -> None:
        image_name = f"frame_{observation.state.frame:06d}.png"
        image_path = self.images_dir / image_name
        image_bgr = cv2.cvtColor(observation.front_camera_rgb, cv2.COLOR_RGB2BGR)
        image_bytes = self._encode_png(image_bgr, image_path)
        self._atomic_write_bytes(image_path, image_bytes)

        # Each manifest line fully describes one frame so the dataset can be streamed back later.
        record = {
            "frame": observation.state.frame,
            "timestamp": observation.state.timestamp,
            "image_path": f"images/{image_name}",
            "image_shape": list(observation.front_camera_rgb.shape),
            "state": observation.state.as_dict(),
            "control": command.as_dict(),
            "requested_control": (
                requested_control.as_dict() if requested_control is not None else None
            ),
            "lane_offset_m": observation.lane_offset_m,
            "heading_error_deg": observation.heading_error_deg,
            "lane_details": observation.lane_details,
            "collision_detected": observation.collision_detected,
            "collision_details": observation.collision_details,
            "obstacle_details": observation.obstacle_details,
            "fleet_message": message.as_dict(),
            "alerts": alerts or [],
        }
        self._manifest_handle.write(json.dumps(record, sort_keys=True) + "\n")
        self._manifest_handle.flush()
        os.fsync(self._manifest_handle.fileno())

        self._frames_recorded += 1
        self._last_frame = observation.state.frame
        if self._frames_recorded == 1 or self._frames_recorded % self._PROGRESS_WRITE_INTERVAL == 0:
            self._write_metadata(status="recording")

    def close(self) -> None:
        self._manifest_handle.flush()
        os.fsync(self._manifest_handle.fileno())
        self._manifest_handle.close()
        self._write_metadata(
            status="completed",
            completed_at=datetime.now().astimezone().isoformat(),
        )

    def _write_metadata(self, status: str, completed_at: str | None = None) -> None:
        metadata = {
            "created_at": self._created_at,
            "completed_at": completed_at,
            "config": asdict(self._config),
            "controller": self._controller_name,
            "frames_recorded": self._frames_recorded,
            "last_frame": self._last_frame,
            "status": status,
        }
        payload = json.dumps(metadata, indent=2, sort_keys=True).encode("utf-8")
        self._atomic_write_bytes(self.metadata_path, payload)

    def _encode_png(self, image_bgr: Any, image_path: Path) -> bytes:
        success, encoded = cv2.imencode(".png", image_bgr)
        if not success:
            raise RuntimeError(f"Failed to encode image: {image_path}")
        return encoded.tobytes()

    def _atomic_write_bytes(self, path: Path, payload: bytes) -> None:
        temp_path = path.with_name(f"{path.name}.tmp")
        with temp_path.open("wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
