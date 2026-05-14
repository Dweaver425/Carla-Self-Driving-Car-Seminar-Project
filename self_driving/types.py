from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np


@dataclass(slots=True)
class Pose2D:
    x: float = 0.0
    y: float = 0.0
    yaw_deg: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ControlCommand:
    throttle: float = 0.0
    steering: float = 0.0
    brake: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class VehicleState:
    vehicle_id: str
    timestamp: float
    pose: Pose2D
    speed_mps: float
    control: ControlCommand = field(default_factory=ControlCommand)
    frame: int = 0

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class DrivingObservation:
    state: VehicleState
    front_camera_rgb: np.ndarray
    lane_offset_m: float | None = None
    heading_error_deg: float | None = None
    collision_detected: bool = False
    collision_details: dict[str, Any] | None = None
    obstacle_details: dict[str, Any] | None = None
