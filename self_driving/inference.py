from __future__ import annotations

from pathlib import Path

import torch

from self_driving.control import clamp
from self_driving.modeling import image_to_tensor, load_driving_model
from self_driving.types import ControlCommand, DrivingObservation


class ModelController:
    def __init__(
        self,
        checkpoint_path: str | Path,
        target_speed_mps: float = 8.0,
        autopilot_guide: bool = False,
        lane_guard: bool = False,
        lane_guard_strength: float = 0.35,
    ) -> None:
        self.model, self.device, self.metadata = load_driving_model(checkpoint_path)
        self.target_speed_mps = target_speed_mps
        self.autopilot_guidance_enabled = autopilot_guide
        self.lane_guard_enabled = lane_guard
        self.lane_guard_strength = clamp(lane_guard_strength, 0.0, 1.0)
        self._last_steering: float | None = None

    def on_client_ready(self, client: object) -> None:
        if not self.autopilot_guidance_enabled:
            return

        enable_autopilot = getattr(client, "enable_autopilot", None)
        if not callable(enable_autopilot):
            raise ValueError("Autopilot guidance is only available with the CARLA backend.")
        enable_autopilot()

    def command(self, observation: DrivingObservation, step: int) -> ControlCommand:
        if observation.collision_detected and not self.autopilot_guidance_enabled:
            return ControlCommand(throttle=0.0, steering=0.0, brake=1.0)

        image_tensor = image_to_tensor(observation.front_camera_rgb).unsqueeze(0).to(self.device)
        with torch.no_grad():
            outputs = self.model(image_tensor).squeeze(0).cpu().tolist()

        # The network is unconstrained, so clamp each output into valid vehicle-control ranges.
        throttle = clamp(float(outputs[0]), 0.0, 1.0)
        steering = clamp(float(outputs[1]), -1.0, 1.0)
        brake = clamp(float(outputs[2]), 0.0, 1.0)

        # The training labels can contain small brake values while the vehicle is
        # trying to launch. In CARLA that can pin the car in place, so treat weak
        # braking as noise while we are still below the target speed.
        if observation.state.speed_mps < self.target_speed_mps and brake < 0.18:
            brake = 0.0

        if observation.state.speed_mps < 1.0 and throttle > 0.2:
            throttle = max(throttle, 0.55)
            brake = 0.0

        # Add a lightweight speed guardrail so an overconfident model does not keep accelerating.
        if observation.state.speed_mps > self.target_speed_mps + 1.0:
            throttle = min(throttle, 0.1)
            brake = max(brake, 0.15)

        # Do not send strong throttle and brake together; keep the command internally consistent.
        if throttle > 0.2 and brake > 0.0 and observation.state.speed_mps < self.target_speed_mps:
            brake = 0.0

        if self.lane_guard_enabled:
            steering, throttle, brake = self._apply_lane_guard(
                observation,
                steering=steering,
                throttle=throttle,
                brake=brake,
            )
            steering = self._smooth_guarded_steering(steering, observation)
        else:
            self._last_steering = steering

        return ControlCommand(throttle=throttle, steering=steering, brake=brake)

    def _apply_lane_guard(
        self,
        observation: DrivingObservation,
        *,
        steering: float,
        throttle: float,
        brake: float,
    ) -> tuple[float, float, float]:
        if observation.lane_offset_m is None or observation.heading_error_deg is None:
            return steering, throttle, brake

        lane_offset = float(observation.lane_offset_m)
        heading_error = float(observation.heading_error_deg)
        abs_lane_offset = abs(lane_offset)
        abs_heading_error = abs(heading_error)
        if abs_lane_offset < 0.25 and abs_heading_error < 3.0:
            return steering, throttle, brake

        lane_correction = clamp(
            (-0.22 * lane_offset) + (-0.045 * heading_error),
            -1.0,
            1.0,
        )
        severity = max(abs_lane_offset / 1.0, abs_heading_error / 12.0)
        blend = clamp(0.15 + (0.2 * severity), 0.0, self.lane_guard_strength)
        guarded_steering = clamp(
            ((1.0 - blend) * steering) + (blend * lane_correction),
            -1.0,
            1.0,
        )

        if abs_lane_offset > 0.9 or abs_heading_error > 14.0:
            throttle = min(throttle, 0.25)
            brake = max(brake, 0.08)

        return guarded_steering, throttle, brake

    def _smooth_guarded_steering(
        self,
        steering: float,
        observation: DrivingObservation,
    ) -> float:
        if self._last_steering is None:
            self._last_steering = steering
            return steering

        abs_heading_error = (
            abs(float(observation.heading_error_deg))
            if observation.heading_error_deg is not None
            else 0.0
        )
        abs_lane_offset = (
            abs(float(observation.lane_offset_m))
            if observation.lane_offset_m is not None
            else 0.0
        )
        # Let urgent corrections move faster, but damp small frame-to-frame jitter.
        max_delta = 0.06
        if abs_lane_offset > 0.75 or abs_heading_error > 10.0:
            max_delta = 0.11

        delta = clamp(steering - self._last_steering, -max_delta, max_delta)
        smoothed = clamp(self._last_steering + delta, -1.0, 1.0)
        self._last_steering = smoothed
        return smoothed
