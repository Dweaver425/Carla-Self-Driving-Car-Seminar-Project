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
    TRAFFIC_LIGHT_CREEP_THROTTLE,
    TRAFFIC_LIGHT_RELEASE_THROTTLE,
)
from self_driving.types import ControlCommand, DrivingObservation, Pose2D, VehicleState


def make_controller() -> ModelController:
    controller = ModelController.__new__(ModelController)
    controller._active_stop_sign_id = None
    controller._stop_hold_steps = 0
    controller._cleared_stop_sign_ids = set()
    return controller


def make_observation(
    speed_mps: float,
    traffic_rule_details: dict | None,
    *,
    lane_offset_m: float | None = 0.0,
    heading_error_deg: float | None = 0.0,
    is_junction: bool = False,
    obstacle_details: dict | None = None,
) -> DrivingObservation:
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
        lane_offset_m=lane_offset_m,
        heading_error_deg=heading_error_deg,
        lane_details={"is_junction": is_junction},
        obstacle_details=obstacle_details,
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

    def test_red_light_creeps_when_stopped_short_of_trigger(self) -> None:
        controller = make_controller()
        observation = make_observation(
            speed_mps=0.0,
            traffic_rule_details={
                "traffic_light": {
                    "id": 1,
                    "state": "Red",
                    "forward_distance_m": 2.66,
                    "trigger_min_forward_m": 2.08,
                }
            },
        )

        throttle, brake = controller._apply_traffic_rule_guard(
            observation,
            throttle=0.0,
            brake=0.95,
        )

        self.assertEqual(throttle, TRAFFIC_LIGHT_CREEP_THROTTLE)
        self.assertEqual(brake, 0.0)

    def test_green_light_releases_leftover_model_brake(self) -> None:
        controller = make_controller()
        observation = make_observation(
            speed_mps=0.0,
            traffic_rule_details={
                "traffic_light": {
                    "id": 1,
                    "state": "Green",
                    "forward_distance_m": 2.66,
                }
            },
        )

        throttle, brake = controller._apply_traffic_rule_guard(
            observation,
            throttle=0.0,
            brake=0.95,
        )

        self.assertEqual(throttle, TRAFFIC_LIGHT_RELEASE_THROTTLE)
        self.assertEqual(brake, 0.0)

    def test_no_rule_does_not_release_model_brake(self) -> None:
        controller = make_controller()
        observation = make_observation(speed_mps=0.0, traffic_rule_details=None)

        throttle, brake = controller._apply_traffic_rule_guard(
            observation,
            throttle=0.0,
            brake=0.9,
        )

        self.assertEqual(throttle, 0.0)
        self.assertEqual(brake, 0.9)

    def test_obstacle_guard_brakes_for_close_object(self) -> None:
        controller = make_controller()
        observation = make_observation(
            speed_mps=4.0,
            traffic_rule_details=None,
            obstacle_details={"distance_m": 2.0},
        )

        throttle, brake = controller._apply_obstacle_guard(
            observation,
            throttle=0.7,
            brake=0.0,
        )

        self.assertEqual(throttle, 0.0)
        self.assertGreaterEqual(brake, 0.8)

    def test_obstacle_guard_slows_for_near_object(self) -> None:
        controller = make_controller()
        observation = make_observation(
            speed_mps=4.0,
            traffic_rule_details=None,
            obstacle_details={"distance_m": 4.0},
        )

        throttle, brake = controller._apply_obstacle_guard(
            observation,
            throttle=0.7,
            brake=0.0,
        )

        self.assertLessEqual(throttle, 0.12)
        self.assertGreaterEqual(brake, 0.2)

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
