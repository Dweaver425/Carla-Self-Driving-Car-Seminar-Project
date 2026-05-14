from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

BackendName = Literal["mock", "carla"]
SpectatorMode = Literal["none", "chase", "hood"]


@dataclass(slots=True)
class SimulationConfig:
    backend: BackendName = "mock"
    host: str = "127.0.0.1"
    port: int = 2000
    traffic_manager_port: int = 8000
    timeout_seconds: float = 10.0
    synchronous_mode: bool = True
    fixed_delta_seconds: float = 0.05
    ego_vehicle_id: str = "ego-001"
    vehicle_blueprint: str = "vehicle.tesla.model3"
    spawn_index: int = 0
    spawn_lateral_offset_m: float = 0.0
    spawn_yaw_offset_deg: float = 0.0
    steps: int = 120
    camera_width: int = 160
    camera_height: int = 90
    camera_fov: int = 100
    spectator_mode: SpectatorMode = "none"
