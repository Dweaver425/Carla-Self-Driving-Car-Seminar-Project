from __future__ import annotations

import math

import cv2
import numpy as np

from self_driving.config import SimulationConfig
from self_driving.simulator.base import SimulatorClient
from self_driving.types import ControlCommand, DrivingObservation, Pose2D, VehicleState


def normalize_angle_deg(value: float) -> float:
    while value > 180.0:
        value -= 360.0
    while value < -180.0:
        value += 360.0
    return value


class MockSimulatorClient(SimulatorClient):
    def __init__(self, config: SimulationConfig) -> None:
        self.config = config
        self._frame = 0
        self._timestamp = 0.0
        self._speed_mps = 0.0
        self._pose = Pose2D()
        self._last_command = ControlCommand()

    def setup(self) -> None:
        self._frame = 0
        self._timestamp = 0.0
        self._speed_mps = 4.0
        self._last_command = ControlCommand()
        self._pose = Pose2D(
            x=0.0,
            y=self._road_center(0.0) + 0.45,
            yaw_deg=self._road_heading_deg(0.0) + 4.0,
        )

    def get_observation(self) -> DrivingObservation:
        return self._build_observation(self._last_command)

    def step(self, command: ControlCommand) -> DrivingObservation:
        delta_t = self.config.fixed_delta_seconds
        acceleration = max(command.throttle, 0.0) * 2.8 - max(command.brake, 0.0) * 5.5
        self._speed_mps = max(0.0, min(14.0, self._speed_mps + acceleration * delta_t))
        self._pose.yaw_deg += command.steering * 18.0

        heading_rad = math.radians(self._pose.yaw_deg)
        self._pose.x += math.cos(heading_rad) * self._speed_mps * delta_t
        self._pose.y += math.sin(heading_rad) * self._speed_mps * delta_t

        self._pose.y += math.sin(self._frame / 18.0) * 0.008
        self._pose.yaw_deg += math.sin(self._frame / 20.0) * 0.08
        self._pose.yaw_deg = normalize_angle_deg(self._pose.yaw_deg)

        self._frame += 1
        self._timestamp += delta_t
        self._last_command = command
        return self._build_observation(command)

    def teardown(self) -> None:
        return None

    def _build_observation(self, command: ControlCommand) -> DrivingObservation:
        lane_center_y = self._road_center(self._pose.x)
        road_heading_deg = self._road_heading_deg(self._pose.x)
        lane_offset_m = self._pose.y - lane_center_y
        heading_error_deg = normalize_angle_deg(self._pose.yaw_deg - road_heading_deg)
        collision_detected = abs(lane_offset_m) > 2.8
        image = self._render_front_camera(lane_offset_m, heading_error_deg, collision_detected)

        state = VehicleState(
            vehicle_id=self.config.ego_vehicle_id,
            timestamp=self._timestamp,
            pose=Pose2D(x=self._pose.x, y=self._pose.y, yaw_deg=self._pose.yaw_deg),
            speed_mps=self._speed_mps,
            control=command,
            frame=self._frame,
        )
        return DrivingObservation(
            state=state,
            front_camera_rgb=image,
            lane_offset_m=lane_offset_m,
            heading_error_deg=heading_error_deg,
            collision_detected=collision_detected,
        )

    def _road_center(self, x: float) -> float:
        return 2.0 * math.sin(x / 18.0)

    def _road_heading_deg(self, x: float) -> float:
        slope = (2.0 / 18.0) * math.cos(x / 18.0)
        return math.degrees(math.atan(slope))

    def _render_front_camera(
        self,
        lane_offset_m: float,
        heading_error_deg: float,
        collision_detected: bool,
    ) -> np.ndarray:
        width = self.config.camera_width
        height = self.config.camera_height
        image = np.zeros((height, width, 3), dtype=np.uint8)

        horizon = int(height * 0.52)
        image[:horizon] = (135, 190, 235)
        image[horizon:] = (78, 132, 78)

        shift_bottom = int((-lane_offset_m * 22.0) + (-heading_error_deg * 1.8))
        shift_top = int((-lane_offset_m * 8.0) + (-heading_error_deg * 3.0))
        road_center_bottom = (width // 2) + shift_bottom
        road_center_top = (width // 2) + shift_top
        road_half_width_bottom = int(width * 0.34)
        road_half_width_top = int(width * 0.12)

        road_polygon = np.array(
            [
                [road_center_bottom - road_half_width_bottom, height - 1],
                [road_center_top - road_half_width_top, horizon],
                [road_center_top + road_half_width_top, horizon],
                [road_center_bottom + road_half_width_bottom, height - 1],
            ],
            dtype=np.int32,
        )
        cv2.fillPoly(image, [road_polygon], color=(58, 58, 58))

        left_bottom = road_center_bottom - int(road_half_width_bottom * 0.55)
        left_top = road_center_top - int(road_half_width_top * 0.55)
        right_bottom = road_center_bottom + int(road_half_width_bottom * 0.55)
        right_top = road_center_top + int(road_half_width_top * 0.55)
        cv2.line(image, (left_bottom, height - 1), (left_top, horizon), (245, 245, 245), 2)
        cv2.line(image, (right_bottom, height - 1), (right_top, horizon), (245, 245, 245), 2)

        for index in range(5):
            start_ratio = 0.58 + (index * 0.07)
            end_ratio = start_ratio + 0.04
            y1 = int(height * start_ratio)
            y2 = int(height * end_ratio)
            x1 = int(road_center_top + (road_center_bottom - road_center_top) * start_ratio)
            x2 = int(road_center_top + (road_center_bottom - road_center_top) * end_ratio)
            cv2.line(image, (x1, y1), (x2, y2), (240, 210, 80), 2)

        if collision_detected:
            cv2.rectangle(
                image,
                (int(width * 0.38), int(height * 0.58)),
                (int(width * 0.62), int(height * 0.82)),
                (200, 60, 60),
                thickness=-1,
            )

        return image
