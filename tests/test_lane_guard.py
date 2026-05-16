from __future__ import annotations

import sys
import types
import unittest

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


class Tensor:
    @classmethod
    def __class_getitem__(cls, item):
        return cls


torch_stub.Tensor = Tensor

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

utils_stub = types.ModuleType("torch.utils")
data_stub = types.ModuleType("torch.utils.data")


class Dataset:
    @classmethod
    def __class_getitem__(cls, item):
        return cls


data_stub.ConcatDataset = lambda *args, **kwargs: None
data_stub.DataLoader = lambda *args, **kwargs: None
data_stub.Dataset = Dataset
data_stub.random_split = lambda *args, **kwargs: []
utils_stub.data = data_stub
torch_stub.utils = utils_stub

sys.modules.setdefault("torch", torch_stub)
sys.modules.setdefault("torch.nn", nn_stub)
sys.modules.setdefault("torch.utils", utils_stub)
sys.modules.setdefault("torch.utils.data", data_stub)

from self_driving.inference import (  # noqa: E402
    LANE_GUARD_JUNCTION_SMOOTHING_BLEND,
    LANE_GUARD_JUNCTION_HEADING_STEERING_LIMIT,
    LANE_GUARD_JUNCTION_HEADING_THROTTLE_LIMIT,
    LANE_GUARD_JUNCTION_MAX_DELTA,
    LANE_GUARD_NORMAL_MAX_DELTA,
    LANE_GUARD_RECOVERY_MAX_DELTA,
    LANE_GUARD_RECOVERY_SMOOTHING_BLEND,
    LANE_GUARD_SMOOTHING_BLEND,
    LANE_GUARD_STEERING_REVERSAL_SCALE,
    ModelController,
)
from self_driving.types import ControlCommand, DrivingObservation, Pose2D, VehicleState  # noqa: E402


def make_controller() -> ModelController:
    controller = ModelController.__new__(ModelController)
    controller.lane_guard_strength = 0.55
    controller._last_steering = None
    return controller


def make_observation(
    *,
    lane_offset_m: float,
    heading_error_deg: float,
    is_junction: bool,
    speed_mps: float = 4.0,
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
        lane_offset_m=lane_offset_m,
        heading_error_deg=heading_error_deg,
        lane_details={"is_junction": is_junction},
    )


class LaneGuardTests(unittest.TestCase):
    def test_junction_lane_guard_is_softer_than_regular_lane_guard(self) -> None:
        controller = make_controller()
        road_observation = make_observation(
            lane_offset_m=0.6,
            heading_error_deg=8.0,
            is_junction=False,
        )
        junction_observation = make_observation(
            lane_offset_m=0.6,
            heading_error_deg=8.0,
            is_junction=True,
        )

        road_steering, _, _ = controller._apply_lane_guard(
            road_observation,
            steering=0.5,
            throttle=0.7,
            brake=0.0,
        )
        junction_steering, _, _ = controller._apply_lane_guard(
            junction_observation,
            steering=0.5,
            throttle=0.7,
            brake=0.0,
        )

        self.assertLess(road_steering, junction_steering)
        self.assertLess(junction_steering, 0.5)

    def test_junction_small_errors_do_not_override_model_steering(self) -> None:
        controller = make_controller()
        observation = make_observation(
            lane_offset_m=0.35,
            heading_error_deg=4.0,
            is_junction=True,
        )

        steering, throttle, brake = controller._apply_lane_guard(
            observation,
            steering=0.2,
            throttle=0.7,
            brake=0.0,
        )

        self.assertEqual(steering, 0.2)
        self.assertEqual(throttle, 0.7)
        self.assertEqual(brake, 0.0)

    def test_junction_heading_only_spike_does_not_force_u_turn(self) -> None:
        controller = make_controller()
        observation = make_observation(
            lane_offset_m=0.06,
            heading_error_deg=107.0,
            is_junction=True,
            speed_mps=5.0,
        )

        steering, throttle, brake = controller._apply_lane_guard(
            observation,
            steering=-0.8,
            throttle=0.6,
            brake=0.0,
        )

        self.assertGreaterEqual(steering, -LANE_GUARD_JUNCTION_HEADING_STEERING_LIMIT)
        self.assertLessEqual(steering, LANE_GUARD_JUNCTION_HEADING_STEERING_LIMIT)
        self.assertLessEqual(throttle, LANE_GUARD_JUNCTION_HEADING_THROTTLE_LIMIT)
        self.assertEqual(brake, 0.0)

    def test_junction_steering_smoothing_uses_smaller_delta(self) -> None:
        controller = make_controller()
        controller._last_steering = 0.0
        observation = make_observation(
            lane_offset_m=0.4,
            heading_error_deg=5.0,
            is_junction=True,
        )

        steering = controller._smooth_guarded_steering(0.2, observation)

        self.assertAlmostEqual(
            steering,
            LANE_GUARD_JUNCTION_MAX_DELTA * LANE_GUARD_JUNCTION_SMOOTHING_BLEND,
        )

    def test_junction_heading_only_spike_uses_junction_smoothing(self) -> None:
        controller = make_controller()
        controller._last_steering = 0.0
        observation = make_observation(
            lane_offset_m=0.06,
            heading_error_deg=107.0,
            is_junction=True,
        )

        steering = controller._smooth_guarded_steering(-1.0, observation)

        self.assertAlmostEqual(
            steering,
            -(LANE_GUARD_JUNCTION_MAX_DELTA * LANE_GUARD_JUNCTION_SMOOTHING_BLEND),
        )

    def test_large_lane_error_overrides_bad_model_turn_and_slows_down(self) -> None:
        controller = make_controller()
        observation = make_observation(
            lane_offset_m=1.25,
            heading_error_deg=20.0,
            is_junction=False,
            speed_mps=4.0,
        )

        steering, throttle, brake = controller._apply_lane_guard(
            observation,
            steering=0.8,
            throttle=0.7,
            brake=0.0,
        )

        self.assertLess(steering, 0.0)
        self.assertEqual(throttle, 0.0)
        self.assertGreaterEqual(brake, 0.35)

    def test_large_lane_error_crawls_when_already_stopped(self) -> None:
        controller = make_controller()
        observation = make_observation(
            lane_offset_m=-0.66,
            heading_error_deg=-22.0,
            is_junction=True,
            speed_mps=0.0,
        )

        steering, throttle, brake = controller._apply_lane_guard(
            observation,
            steering=0.8,
            throttle=0.7,
            brake=0.0,
        )

        self.assertGreater(steering, 0.0)
        self.assertGreater(throttle, 0.0)
        self.assertLessEqual(throttle, 0.18)
        self.assertEqual(brake, 0.0)

    def test_junction_recovery_stops_softening_when_lane_error_is_large(self) -> None:
        controller = make_controller()
        observation = make_observation(
            lane_offset_m=1.0,
            heading_error_deg=14.0,
            is_junction=True,
            speed_mps=4.0,
        )

        steering, throttle, brake = controller._apply_lane_guard(
            observation,
            steering=0.5,
            throttle=0.7,
            brake=0.0,
        )

        self.assertLess(steering, 0.0)
        self.assertLessEqual(throttle, 0.18)
        self.assertGreaterEqual(brake, 0.12)

    def test_recovery_smoothing_allows_faster_correction(self) -> None:
        controller = make_controller()
        controller._last_steering = 0.0
        observation = make_observation(
            lane_offset_m=1.0,
            heading_error_deg=12.0,
            is_junction=True,
        )

        steering = controller._smooth_guarded_steering(-0.5, observation)

        self.assertAlmostEqual(
            steering,
            -(LANE_GUARD_RECOVERY_MAX_DELTA * LANE_GUARD_RECOVERY_SMOOTHING_BLEND),
        )

    def test_steering_reversal_is_damped_to_reduce_zigzag(self) -> None:
        controller = make_controller()
        controller._last_steering = 0.3
        observation = make_observation(
            lane_offset_m=0.5,
            heading_error_deg=5.0,
            is_junction=False,
        )

        steering = controller._smooth_guarded_steering(-0.4, observation)

        expected_delta = (
            LANE_GUARD_NORMAL_MAX_DELTA
            * LANE_GUARD_STEERING_REVERSAL_SCALE
            * LANE_GUARD_SMOOTHING_BLEND
        )
        self.assertAlmostEqual(steering, 0.3 - expected_delta)


if __name__ == "__main__":
    unittest.main()
