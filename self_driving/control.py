from __future__ import annotations

from typing import Protocol

from self_driving.types import ControlCommand, DrivingObservation


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


class Controller(Protocol):
    def command(self, observation: DrivingObservation, step: int) -> ControlCommand:
        """Return the next low-level control command."""


class DemoController:
    def command(self, observation: DrivingObservation, step: int) -> ControlCommand:
        # Alternate between gentle left and right steering so the demo visibly moves.
        phase = step % 80
        steering = 0.16 if phase < 40 else -0.16
        throttle = 0.42 if observation.state.speed_mps < 6.0 else 0.24
        return ControlCommand(throttle=throttle, steering=steering, brake=0.0)


class LaneKeepingController:
    def __init__(self, target_speed_mps: float = 8.0) -> None:
        self.target_speed_mps = target_speed_mps

    def command(self, observation: DrivingObservation, step: int) -> ControlCommand:
        if observation.collision_detected:
            return ControlCommand(throttle=0.0, steering=0.0, brake=1.0)

        lane_offset = observation.lane_offset_m or 0.0
        heading_error = observation.heading_error_deg or 0.0

        # Combine lateral error and heading error into a simple steering correction.
        steering = clamp((-0.22 * lane_offset) + (-0.045 * heading_error), -1.0, 1.0)

        speed_error = self.target_speed_mps - observation.state.speed_mps
        throttle = clamp(0.28 + (0.06 * speed_error) - (0.12 * abs(steering)), 0.0, 0.75)
        brake = clamp((-0.08 * speed_error), 0.0, 1.0) if speed_error < -1.0 else 0.0
        return ControlCommand(throttle=throttle, steering=steering, brake=brake)
