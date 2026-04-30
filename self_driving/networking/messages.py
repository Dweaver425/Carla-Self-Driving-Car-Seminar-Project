from __future__ import annotations

from dataclasses import asdict, dataclass, field
from math import cos, radians, sin
from typing import Any

from self_driving.types import DrivingObservation, VehicleState


@dataclass(slots=True)
class FleetMessage:
    vehicle_id: str
    frame: int
    timestamp: float
    x: float
    y: float
    yaw_deg: float
    speed_mps: float
    predicted_path: list[tuple[float, float]] = field(default_factory=list)
    confidence: float = 1.0

    @classmethod
    def from_state(
        cls,
        state: VehicleState,
        horizon_steps: int = 3,
        step_distance_m: float = 2.0,
    ) -> "FleetMessage":
        heading_rad = radians(state.pose.yaw_deg)
        projected_step = max(step_distance_m, state.speed_mps * 0.5)
        predicted_path = [
            (
                state.pose.x + cos(heading_rad) * projected_step * (index + 1),
                state.pose.y + sin(heading_rad) * projected_step * (index + 1),
            )
            for index in range(horizon_steps)
        ]
        return cls(
            vehicle_id=state.vehicle_id,
            frame=state.frame,
            timestamp=state.timestamp,
            x=state.pose.x,
            y=state.pose.y,
            yaw_deg=state.pose.yaw_deg,
            speed_mps=state.speed_mps,
            predicted_path=predicted_path,
        )

    @classmethod
    def from_observation(cls, observation: DrivingObservation) -> "FleetMessage":
        return cls.from_state(observation.state)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "FleetMessage":
        path = [
            (float(point[0]), float(point[1]))
            for point in payload.get("predicted_path", [])
        ]
        return cls(
            vehicle_id=str(payload["vehicle_id"]),
            frame=int(payload.get("frame", 0)),
            timestamp=float(payload["timestamp"]),
            x=float(payload["x"]),
            y=float(payload["y"]),
            yaw_deg=float(payload["yaw_deg"]),
            speed_mps=float(payload["speed_mps"]),
            predicted_path=path,
            confidence=float(payload.get("confidence", 1.0)),
        )

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class CollisionAlert:
    subject_vehicle_id: str
    other_vehicle_id: str
    timestamp: float
    distance_m: float
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)
