from __future__ import annotations

from pathlib import Path

import torch

from self_driving.control import clamp
from self_driving.modeling import image_to_tensor, load_driving_model
from self_driving.types import ControlCommand, DrivingObservation

STOP_HOLD_STEPS = 25
TRAFFIC_LIGHT_STOP_BUFFER_M = 2.0
TRAFFIC_LIGHT_LOOKAHEAD_M = 24.0
TRAFFIC_LIGHT_DEFAULT_STOP_TARGET_M = 1.5
TRAFFIC_LIGHT_TRIGGER_STOP_MARGIN_M = 0.25
TRAFFIC_LIGHT_CREEP_LOOKAHEAD_M = 6.0
TRAFFIC_LIGHT_CREEP_SPEED_MPS = 0.7
TRAFFIC_LIGHT_CREEP_THROTTLE = 0.14
TRAFFIC_LIGHT_RELEASE_SPEED_MPS = 0.5
TRAFFIC_LIGHT_RELEASE_THROTTLE = 0.45
STOP_SIGN_LOOKAHEAD_M = 20.0
STOP_SIGN_COMMITTED_PAST_BUFFER_M = 8.0
STOP_SIGN_HARD_BRAKE_DISTANCE_M = 6.0
STOP_SIGN_STOPPED_SPEED_MPS = 0.08
MODEL_FALSE_STOP_SPEED_MPS = 0.35
MODEL_FALSE_STOP_BRAKE_THRESHOLD = 0.35
MODEL_FALSE_STOP_RELEASE_THROTTLE = 0.38
LANE_GUARD_JUNCTION_BLEND_SCALE = 0.45
LANE_GUARD_JUNCTION_GAIN_SCALE = 0.6
LANE_GUARD_JUNCTION_DEADBAND_OFFSET_M = 0.45
LANE_GUARD_JUNCTION_DEADBAND_HEADING_DEG = 6.0
LANE_GUARD_JUNCTION_MAX_DELTA = 0.04
LANE_GUARD_JUNCTION_URGENT_MAX_DELTA = 0.08


class ModelController:
    def __init__(
        self,
        checkpoint_path: str | Path,
        target_speed_mps: float = 8.0,
        autopilot_guide: bool = False,
        lane_guard: bool = False,
        lane_guard_strength: float = 0.35,
        traffic_rule_guard: bool = False,
    ) -> None:
        self.model, self.device, self.metadata = load_driving_model(checkpoint_path)
        self.target_speed_mps = target_speed_mps
        self.autopilot_guidance_enabled = autopilot_guide
        self.lane_guard_enabled = lane_guard
        self.lane_guard_strength = clamp(lane_guard_strength, 0.0, 1.0)
        self.traffic_rule_guard_enabled = traffic_rule_guard
        self._last_steering: float | None = None
        self._active_stop_sign_id: int | None = None
        self._stop_hold_steps = 0
        self._cleared_stop_sign_ids: set[int] = set()

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

        if self.traffic_rule_guard_enabled:
            throttle, brake = self._apply_traffic_rule_guard(
                observation,
                throttle=throttle,
                brake=brake,
            )
            throttle, brake = self._release_model_false_stop(
                observation,
                throttle=throttle,
                brake=brake,
            )

        return ControlCommand(throttle=throttle, steering=steering, brake=brake)

    def _apply_traffic_rule_guard(
        self,
        observation: DrivingObservation,
        *,
        throttle: float,
        brake: float,
    ) -> tuple[float, float]:
        details = observation.traffic_rule_details or {}
        traffic_light = details.get("traffic_light")
        release_for_green_light = False
        if isinstance(traffic_light, dict) and traffic_light.get("state") in {"Red", "Yellow"}:
            forward_distance = float(traffic_light.get("forward_distance_m", 999.0))
            if (
                traffic_light.get("state") == "Red"
                and observation.state.speed_mps < TRAFFIC_LIGHT_CREEP_SPEED_MPS
                and forward_distance <= TRAFFIC_LIGHT_CREEP_LOOKAHEAD_M
                and forward_distance > self._traffic_light_stop_target(traffic_light)
            ):
                return TRAFFIC_LIGHT_CREEP_THROTTLE, 0.0
            if self._must_stop_for_rule(
                observation,
                forward_distance_m=forward_distance,
                max_lookahead_m=TRAFFIC_LIGHT_LOOKAHEAD_M,
            ):
                return 0.0, max(brake, self._brake_for_rule_stop(observation))
        elif isinstance(traffic_light, dict) and traffic_light.get("state") == "Green":
            forward_distance = float(traffic_light.get("forward_distance_m", 999.0))
            release_for_green_light = (
                observation.state.speed_mps < TRAFFIC_LIGHT_RELEASE_SPEED_MPS
                and forward_distance <= TRAFFIC_LIGHT_LOOKAHEAD_M
                and forward_distance >= -TRAFFIC_LIGHT_STOP_BUFFER_M
            )

        stop_sign = details.get("stop_sign")
        if not isinstance(stop_sign, dict):
            self._active_stop_sign_id = None
            self._stop_hold_steps = 0
            return self._apply_green_light_release(
                enabled=release_for_green_light,
                throttle=throttle,
                brake=brake,
            )

        stop_id = int(stop_sign.get("id", -1))
        forward_distance = float(stop_sign.get("forward_distance_m", 999.0))
        if stop_id in self._cleared_stop_sign_ids:
            return self._apply_green_light_release(
                enabled=release_for_green_light,
                throttle=throttle,
                brake=brake,
            )

        already_committed = self._active_stop_sign_id == stop_id
        must_stop = self._must_stop_for_rule(
            observation,
            forward_distance_m=forward_distance,
            max_lookahead_m=STOP_SIGN_LOOKAHEAD_M,
        )
        still_finishing_committed_stop = (
            already_committed
            and forward_distance >= -STOP_SIGN_COMMITTED_PAST_BUFFER_M
        )
        if not must_stop and not still_finishing_committed_stop:
            return self._apply_green_light_release(
                enabled=release_for_green_light,
                throttle=throttle,
                brake=brake,
            )

        if self._active_stop_sign_id != stop_id:
            self._active_stop_sign_id = stop_id
            self._stop_hold_steps = 0

        if observation.state.speed_mps > STOP_SIGN_STOPPED_SPEED_MPS:
            self._stop_hold_steps = 0
            rule_brake = self._brake_for_rule_stop(observation)
            if forward_distance <= STOP_SIGN_HARD_BRAKE_DISTANCE_M:
                rule_brake = 1.0
            return 0.0, max(brake, rule_brake)

        self._stop_hold_steps += 1
        if self._stop_hold_steps < STOP_HOLD_STEPS:
            return 0.0, 1.0

        self._cleared_stop_sign_ids.add(stop_id)
        self._active_stop_sign_id = None
        self._stop_hold_steps = 0
        return self._apply_green_light_release(
            enabled=release_for_green_light,
            throttle=throttle,
            brake=brake,
        )

    def _must_stop_for_rule(
        self,
        observation: DrivingObservation,
        *,
        forward_distance_m: float,
        max_lookahead_m: float,
    ) -> bool:
        if forward_distance_m < -TRAFFIC_LIGHT_STOP_BUFFER_M:
            return False
        if forward_distance_m <= 1.0:
            return True

        # Start braking earlier at higher speed. This approximates a comfortable
        # stopping distance without needing CARLA-specific traffic-light geometry.
        speed = max(float(observation.state.speed_mps), 0.0)
        stopping_distance = 2.0 + (speed * 1.2) + ((speed * speed) / 7.0)
        return forward_distance_m <= min(max_lookahead_m, stopping_distance)

    def _brake_for_rule_stop(self, observation: DrivingObservation) -> float:
        if observation.state.speed_mps > 6.0:
            return 1.0
        if observation.state.speed_mps > 3.5:
            return 0.9
        if observation.state.speed_mps > 1.0:
            return 0.7
        return 1.0

    def _traffic_light_stop_target(self, traffic_light: dict[str, object]) -> float:
        trigger_min = traffic_light.get("trigger_min_forward_m")
        try:
            trigger_min_m = float(trigger_min)
        except (TypeError, ValueError):
            return TRAFFIC_LIGHT_DEFAULT_STOP_TARGET_M

        if trigger_min_m <= 0.0:
            return TRAFFIC_LIGHT_DEFAULT_STOP_TARGET_M
        return clamp(
            trigger_min_m - TRAFFIC_LIGHT_TRIGGER_STOP_MARGIN_M,
            1.0,
            2.5,
        )

    def _apply_green_light_release(
        self,
        *,
        enabled: bool,
        throttle: float,
        brake: float,
    ) -> tuple[float, float]:
        if not enabled:
            return throttle, brake
        return max(throttle, TRAFFIC_LIGHT_RELEASE_THROTTLE), 0.0

    def _release_model_false_stop(
        self,
        observation: DrivingObservation,
        *,
        throttle: float,
        brake: float,
    ) -> tuple[float, float]:
        if self._has_active_rule_stop(observation):
            return throttle, brake
        if (
            observation.state.speed_mps <= MODEL_FALSE_STOP_SPEED_MPS
            and brake >= MODEL_FALSE_STOP_BRAKE_THRESHOLD
        ):
            return max(throttle, MODEL_FALSE_STOP_RELEASE_THROTTLE), 0.0
        return throttle, brake

    def _has_active_rule_stop(self, observation: DrivingObservation) -> bool:
        details = observation.traffic_rule_details or {}
        traffic_light = details.get("traffic_light")
        if isinstance(traffic_light, dict) and traffic_light.get("state") in {"Red", "Yellow"}:
            forward_distance = float(traffic_light.get("forward_distance_m", 999.0))
            return self._must_stop_for_rule(
                observation,
                forward_distance_m=forward_distance,
                max_lookahead_m=TRAFFIC_LIGHT_LOOKAHEAD_M,
            )

        stop_sign = details.get("stop_sign")
        if not isinstance(stop_sign, dict):
            return False
        stop_id = int(stop_sign.get("id", -1))
        if stop_id in self._cleared_stop_sign_ids:
            return False

        forward_distance = float(stop_sign.get("forward_distance_m", 999.0))
        return (
            self._must_stop_for_rule(
                observation,
                forward_distance_m=forward_distance,
                max_lookahead_m=STOP_SIGN_LOOKAHEAD_M,
            )
            or (
                self._active_stop_sign_id == stop_id
                and forward_distance >= -STOP_SIGN_COMMITTED_PAST_BUFFER_M
            )
        )

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
        is_junction = self._is_junction(observation)
        if (
            is_junction
            and abs_lane_offset < LANE_GUARD_JUNCTION_DEADBAND_OFFSET_M
            and abs_heading_error < LANE_GUARD_JUNCTION_DEADBAND_HEADING_DEG
        ):
            return steering, throttle, brake
        if abs_lane_offset < 0.25 and abs_heading_error < 3.0:
            return steering, throttle, brake

        correction_scale = LANE_GUARD_JUNCTION_GAIN_SCALE if is_junction else 1.0
        lane_correction = clamp(
            correction_scale * ((-0.22 * lane_offset) + (-0.045 * heading_error)),
            -1.0,
            1.0,
        )
        severity = max(abs_lane_offset / 1.0, abs_heading_error / 12.0)
        blend = clamp(0.15 + (0.2 * severity), 0.0, self.lane_guard_strength)
        if is_junction:
            blend *= LANE_GUARD_JUNCTION_BLEND_SCALE
        guarded_steering = clamp(
            ((1.0 - blend) * steering) + (blend * lane_correction),
            -1.0,
            1.0,
        )

        slow_for_lane_error = abs_lane_offset > 0.9 or abs_heading_error > 14.0
        if is_junction:
            slow_for_lane_error = abs_lane_offset > 1.2 or abs_heading_error > 20.0
        if slow_for_lane_error:
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
        if self._is_junction(observation):
            max_delta = LANE_GUARD_JUNCTION_MAX_DELTA
            if abs_lane_offset > 0.9 or abs_heading_error > 14.0:
                max_delta = LANE_GUARD_JUNCTION_URGENT_MAX_DELTA
        else:
            max_delta = 0.06
            if abs_lane_offset > 0.75 or abs_heading_error > 10.0:
                max_delta = 0.11

        delta = clamp(steering - self._last_steering, -max_delta, max_delta)
        smoothed = clamp(self._last_steering + delta, -1.0, 1.0)
        self._last_steering = smoothed
        return smoothed

    def _is_junction(self, observation: DrivingObservation) -> bool:
        lane_details = observation.lane_details
        return isinstance(lane_details, dict) and bool(lane_details.get("is_junction"))
