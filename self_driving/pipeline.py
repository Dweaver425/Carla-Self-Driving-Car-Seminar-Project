from __future__ import annotations

import json
from typing import Any

from self_driving.control import Controller
from self_driving.data.recording import EpisodeRecorder
from self_driving.networking.client import TelemetryPublisher
from self_driving.networking.messages import FleetMessage
from self_driving.simulator.base import SimulatorClient


def run_loop(
    client: SimulatorClient,
    controller: Controller,
    steps: int,
    recorder: EpisodeRecorder | None = None,
    publisher: TelemetryPublisher | None = None,
    print_payload: bool = True,
) -> dict[str, Any]:
    client.setup()
    alerts_count = 0
    autopilot_guidance_enabled = bool(
        getattr(controller, "autopilot_guidance_enabled", False)
    )

    try:
        on_client_ready = getattr(controller, "on_client_ready", None)
        if callable(on_client_ready):
            on_client_ready(client)

        observation = client.get_observation()
        start_state = observation.state
        previous_pose = start_state.pose
        distance_traveled_m = 0.0
        max_speed_mps = start_state.speed_mps
        total_speed_mps = 0.0
        total_throttle = 0.0
        total_brake = 0.0
        any_collision_detected = observation.collision_detected
        collision_count = 1 if observation.collision_detected else 0
        first_collision_step = 0 if observation.collision_detected else None
        first_collision_details = observation.collision_details
        last_collision_details = observation.collision_details
        closest_obstacle_distance_m: float | None = None
        closest_obstacle_details: dict[str, Any] | None = None
        lane_metric_samples = 0
        total_abs_lane_offset_m = 0.0
        max_abs_lane_offset_m = 0.0
        total_abs_heading_error_deg = 0.0
        max_abs_heading_error_deg = 0.0
        blocked_detected = False
        first_blocked_step: int | None = None
        blocked_steps = 0
        total_abs_control_delta = {
            "throttle": 0.0,
            "steering": 0.0,
            "brake": 0.0,
        }
        max_abs_control_delta = {
            "throttle": 0.0,
            "steering": 0.0,
            "brake": 0.0,
        }
        for step in range(steps):
            command = controller.command(observation, step)
            observation = client.step(command)
            applied_command = observation.state.control
            control_delta = {
                "throttle": applied_command.throttle - command.throttle,
                "steering": applied_command.steering - command.steering,
                "brake": applied_command.brake - command.brake,
            }
            if autopilot_guidance_enabled:
                for key, value in control_delta.items():
                    abs_value = abs(value)
                    total_abs_control_delta[key] += abs_value
                    max_abs_control_delta[key] = max(max_abs_control_delta[key], abs_value)
            pose = observation.state.pose
            step_distance_m = (
                (pose.x - previous_pose.x) ** 2
                + (pose.y - previous_pose.y) ** 2
            ) ** 0.5
            distance_traveled_m += step_distance_m
            previous_pose = pose
            max_speed_mps = max(max_speed_mps, observation.state.speed_mps)
            total_speed_mps += observation.state.speed_mps
            total_throttle += applied_command.throttle
            total_brake += applied_command.brake

            if observation.collision_detected:
                any_collision_detected = True
                collision_count += 1
                last_collision_details = observation.collision_details
                if first_collision_step is None:
                    first_collision_step = step
                    first_collision_details = observation.collision_details

            if observation.obstacle_details is not None:
                obstacle_distance = observation.obstacle_details.get("distance_m")
                if isinstance(obstacle_distance, int | float) and (
                    closest_obstacle_distance_m is None
                    or obstacle_distance < closest_obstacle_distance_m
                ):
                    closest_obstacle_distance_m = float(obstacle_distance)
                    closest_obstacle_details = observation.obstacle_details

            if observation.lane_offset_m is not None:
                lane_metric_samples += 1
                abs_lane_offset = abs(float(observation.lane_offset_m))
                total_abs_lane_offset_m += abs_lane_offset
                max_abs_lane_offset_m = max(max_abs_lane_offset_m, abs_lane_offset)
            if observation.heading_error_deg is not None:
                abs_heading_error = abs(float(observation.heading_error_deg))
                total_abs_heading_error_deg += abs_heading_error
                max_abs_heading_error_deg = max(
                    max_abs_heading_error_deg,
                    abs_heading_error,
                )

            commanded_to_move = applied_command.throttle > 0.25 and applied_command.brake < 0.2
            not_moving = observation.state.speed_mps < 0.35 and step_distance_m < 0.03
            if step > 20 and commanded_to_move and not_moving:
                blocked_steps += 1
            else:
                blocked_steps = 0
            if not blocked_detected and blocked_steps >= 20:
                blocked_detected = True
                first_blocked_step = step

            message = FleetMessage.from_observation(observation)
            alerts = publisher.publish(message) if publisher else []
            alerts_count += len(alerts)

            # Recording and telemetry both use the same post-step snapshot so the
            # dataset, logs, and fleet messages stay aligned frame by frame.
            if recorder is not None:
                requested_control = command if autopilot_guidance_enabled else None
                recorder.record(
                    observation,
                    applied_command,
                    message,
                    alerts,
                    requested_control=requested_control,
                )

            if print_payload:
                payload: dict[str, Any] = {
                    "step": step,
                    "control": applied_command.as_dict(),
                    "state": observation.state.as_dict(),
                    "fleet_message": message.as_dict(),
                    "collision_detected": observation.collision_detected,
                }
                if autopilot_guidance_enabled:
                    payload["model_control"] = command.as_dict()
                    payload["autopilot_control"] = applied_command.as_dict()
                    payload["control_delta"] = control_delta
                if observation.collision_details is not None:
                    payload["collision_details"] = observation.collision_details
                if observation.obstacle_details is not None:
                    payload["obstacle_details"] = observation.obstacle_details
                if observation.lane_offset_m is not None:
                    payload["lane_offset_m"] = observation.lane_offset_m
                if observation.heading_error_deg is not None:
                    payload["heading_error_deg"] = observation.heading_error_deg
                if observation.lane_details is not None:
                    payload["lane_details"] = observation.lane_details
                if alerts:
                    payload["alerts"] = alerts
                print(json.dumps(payload, sort_keys=True))
    finally:
        if recorder is not None:
            recorder.close()
        # Always tear the simulator down, even if a run fails mid-loop.
        client.teardown()

    final_state = observation.state
    summary = {
        "alerts": alerts_count,
        "autopilot_guidance_enabled": autopilot_guidance_enabled,
        "average_brake": total_brake / max(steps, 1),
        "average_abs_heading_error_deg": total_abs_heading_error_deg
        / max(lane_metric_samples, 1),
        "average_abs_lane_offset_m": total_abs_lane_offset_m
        / max(lane_metric_samples, 1),
        "average_speed_mps": total_speed_mps / max(steps, 1),
        "average_throttle": total_throttle / max(steps, 1),
        "blocked_detected": blocked_detected,
        "carla_collision_detected": any_collision_detected,
        "closest_obstacle_details": closest_obstacle_details,
        "closest_obstacle_distance_m": closest_obstacle_distance_m,
        "collision_count": collision_count,
        "collision_detected": any_collision_detected or blocked_detected,
        "distance_traveled_m": distance_traveled_m,
        "final_pose": final_state.pose.as_dict(),
        "final_lane_details": observation.lane_details,
        "final_speed_mps": final_state.speed_mps,
        "first_blocked_step": first_blocked_step,
        "first_collision_details": first_collision_details,
        "first_collision_step": first_collision_step,
        "frames": final_state.frame,
        "last_collision_details": last_collision_details,
        "lane_metric_samples": lane_metric_samples,
        "max_abs_heading_error_deg": max_abs_heading_error_deg,
        "max_abs_lane_offset_m": max_abs_lane_offset_m,
        "max_speed_mps": max_speed_mps,
        "start_pose": start_state.pose.as_dict(),
        "steps": steps,
        "vehicle_id": final_state.vehicle_id,
    }
    if autopilot_guidance_enabled:
        summary["average_abs_control_delta"] = {
            key: value / max(steps, 1) for key, value in total_abs_control_delta.items()
        }
        summary["max_abs_control_delta"] = max_abs_control_delta
    return summary
