from __future__ import annotations

import unittest
import sys
import types

import numpy as np

torch_stub = types.ModuleType("torch")
torch_stub.backends = types.SimpleNamespace(
    mps=types.SimpleNamespace(is_available=lambda: False)
)
torch_stub.cuda = types.SimpleNamespace(is_available=lambda: False)
torch_stub.device = lambda name: name
torch_stub.from_numpy = lambda array: array
torch_stub.load = lambda *args, **kwargs: {}
torch_stub.no_grad = lambda: None

nn_stub = types.ModuleType("torch.nn")


class Module:
    pass


nn_stub.Module = Module
nn_stub.Sequential = lambda *args, **kwargs: None
nn_stub.Conv2d = lambda *args, **kwargs: None
nn_stub.ReLU = lambda *args, **kwargs: None
nn_stub.AdaptiveAvgPool2d = lambda *args, **kwargs: None
nn_stub.Flatten = lambda *args, **kwargs: None
nn_stub.Linear = lambda *args, **kwargs: None
torch_stub.nn = nn_stub

sys.modules.setdefault("torch", torch_stub)
sys.modules.setdefault("torch.nn", nn_stub)

from self_driving.inference import (
    ModelController,
    STOP_HOLD_STEPS,
    STOP_SIGN_STOPPED_SPEED_MPS,
)
from self_driving.types import ControlCommand, DrivingObservation, Pose2D, VehicleState


def make_controller() -> ModelController:
    controller = ModelController.__new__(ModelController)
    controller._active_stop_sign_id = None
    controller._stop_hold_steps = 0
    controller._cleared_stop_sign_ids = set()
    return controller


def make_observation(speed_mps: float, traffic_rule_details: dict | None) -> DrivingObservation:
    return DrivingObservation(
        state=VehicleState(
            vehicle_id="ego-test",
            timestamp=0.0,
            pose=Pose2D(),
            speed_mps=speed_mps,
            control=ControlCommand(),
        ),
        front_camera_rgb=np.zeros((2, 2, 3), dtype=np.uint8),
        traffic_rule_details=traffic_rule_details,
    )


class TrafficRuleGuardTests(unittest.TestCase):
    def test_red_light_inside_stopping_distance_forces_brake(self) -> None:
        controller = make_controller()
        observation = make_observation(
            speed_mps=8.0,
            traffic_rule_details={
                "traffic_light": {
                    "id": 1,
                    "state": "Red",
                    "forward_distance_m": 18.0,
                }
            },
        )

        throttle, brake = controller._apply_traffic_rule_guard(
            observation,
            throttle=0.6,
            brake=0.0,
        )

        self.assertEqual(throttle, 0.0)
        self.assertEqual(brake, 1.0)

    def test_red_light_beyond_lookahead_does_not_override(self) -> None:
        controller = make_controller()
        observation = make_observation(
            speed_mps=2.0,
            traffic_rule_details={
                "traffic_light": {
                    "id": 1,
                    "state": "Red",
                    "forward_distance_m": 22.0,
                }
            },
        )

        throttle, brake = controller._apply_traffic_rule_guard(
            observation,
            throttle=0.4,
            brake=0.0,
        )

        self.assertEqual(throttle, 0.4)
        self.assertEqual(brake, 0.0)

    def test_stop_sign_requires_full_hold_before_clear(self) -> None:
        controller = make_controller()
        observation = make_observation(
            speed_mps=0.0,
            traffic_rule_details={
                "stop_sign": {
                    "id": 7,
                    "state": "Stop",
                    "forward_distance_m": 1.0,
                }
            },
        )

        for _ in range(STOP_HOLD_STEPS - 1):
            throttle, brake = controller._apply_traffic_rule_guard(
                observation,
                throttle=0.5,
                brake=0.0,
            )
            self.assertEqual(throttle, 0.0)
            self.assertEqual(brake, 1.0)

        throttle, brake = controller._apply_traffic_rule_guard(
            observation,
            throttle=0.5,
            brake=0.0,
        )

        self.assertEqual(throttle, 0.5)
        self.assertEqual(brake, 0.0)
        self.assertIn(7, controller._cleared_stop_sign_ids)

    def test_committed_stop_sign_keeps_braking_after_sign_moves_behind(self) -> None:
        controller = make_controller()
        controller._active_stop_sign_id = 7
        observation = make_observation(
            speed_mps=0.2,
            traffic_rule_details={
                "stop_sign": {
                    "id": 7,
                    "state": "Stop",
                    "forward_distance_m": -3.0,
                }
            },
        )

        throttle, brake = controller._apply_traffic_rule_guard(
            observation,
            throttle=0.5,
            brake=0.0,
        )

        self.assertEqual(throttle, 0.0)
        self.assertEqual(brake, 1.0)
        self.assertNotIn(7, controller._cleared_stop_sign_ids)

    def test_stop_sign_does_not_clear_while_still_rolling(self) -> None:
        controller = make_controller()
        observation = make_observation(
            speed_mps=STOP_SIGN_STOPPED_SPEED_MPS + 0.01,
            traffic_rule_details={
                "stop_sign": {
                    "id": 7,
                    "state": "Stop",
                    "forward_distance_m": 0.5,
                }
            },
        )

        throttle, brake = controller._apply_traffic_rule_guard(
            observation,
            throttle=0.5,
            brake=0.0,
        )

        self.assertEqual(throttle, 0.0)
        self.assertEqual(brake, 1.0)
        self.assertEqual(controller._stop_hold_steps, 0)
        self.assertNotIn(7, controller._cleared_stop_sign_ids)


if __name__ == "__main__":
    unittest.main()
