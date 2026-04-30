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
    observation = client.get_observation()
    alerts_count = 0

    try:
        for step in range(steps):
            command = controller.command(observation, step)
            observation = client.step(command)
            message = FleetMessage.from_observation(observation)
            alerts = publisher.publish(message) if publisher else []
            alerts_count += len(alerts)

            # Recording and telemetry both use the same post-step snapshot so the
            # dataset, logs, and fleet messages stay aligned frame by frame.
            if recorder is not None:
                recorder.record(observation, command, message, alerts)

            if print_payload:
                payload: dict[str, Any] = {
                    "step": step,
                    "control": command.as_dict(),
                    "state": observation.state.as_dict(),
                    "fleet_message": message.as_dict(),
                    "collision_detected": observation.collision_detected,
                }
                if observation.lane_offset_m is not None:
                    payload["lane_offset_m"] = observation.lane_offset_m
                if observation.heading_error_deg is not None:
                    payload["heading_error_deg"] = observation.heading_error_deg
                if alerts:
                    payload["alerts"] = alerts
                print(json.dumps(payload, sort_keys=True))
    finally:
        if recorder is not None:
            recorder.close()
        # Always tear the simulator down, even if a run fails mid-loop.
        client.teardown()

    final_state = observation.state
    return {
        "alerts": alerts_count,
        "collision_detected": observation.collision_detected,
        "final_pose": final_state.pose.as_dict(),
        "final_speed_mps": final_state.speed_mps,
        "frames": final_state.frame,
        "steps": steps,
        "vehicle_id": final_state.vehicle_id,
    }
