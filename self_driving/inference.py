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
    ) -> None:
        self.model, self.device, self.metadata = load_driving_model(checkpoint_path)
        self.target_speed_mps = target_speed_mps

    def command(self, observation: DrivingObservation, step: int) -> ControlCommand:
        if observation.collision_detected:
            return ControlCommand(throttle=0.0, steering=0.0, brake=1.0)

        image_tensor = image_to_tensor(observation.front_camera_rgb).unsqueeze(0).to(self.device)
        with torch.no_grad():
            outputs = self.model(image_tensor).squeeze(0).cpu().tolist()

        # The network is unconstrained, so clamp each output into valid vehicle-control ranges.
        throttle = clamp(float(outputs[0]), 0.0, 1.0)
        steering = clamp(float(outputs[1]), -1.0, 1.0)
        brake = clamp(float(outputs[2]), 0.0, 1.0)

        # Add a lightweight speed guardrail so an overconfident model does not keep accelerating.
        if observation.state.speed_mps > self.target_speed_mps + 1.0:
            throttle = min(throttle, 0.1)
            brake = max(brake, 0.15)

        # Do not send strong throttle and brake together; keep the command internally consistent.
        if throttle > 0.2 and brake > 0.2:
            brake = 0.0

        return ControlCommand(throttle=throttle, steering=steering, brake=brake)
