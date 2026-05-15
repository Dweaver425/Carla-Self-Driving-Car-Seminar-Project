from __future__ import annotations

import types
import unittest

from self_driving.simulator.carla_adapter import CarlaSimulatorClient


class CarlaStopSignFilterTests(unittest.TestCase):
    def test_rejects_stop_sign_on_opposite_lane(self) -> None:
        client = CarlaSimulatorClient.__new__(CarlaSimulatorClient)
        ego_waypoint = types.SimpleNamespace(road_id=10, lane_id=1)

        self.assertFalse(
            client._is_stop_sign_for_ego_lane(
                {"road_id": 10, "lane_id": -1},
                ego_waypoint,
            )
        )

    def test_accepts_stop_sign_on_same_lane(self) -> None:
        client = CarlaSimulatorClient.__new__(CarlaSimulatorClient)
        ego_waypoint = types.SimpleNamespace(road_id=10, lane_id=1, lane_width=3.5)

        self.assertTrue(
            client._is_stop_sign_for_ego_lane(
                {"road_id": 10, "lane_id": 1},
                ego_waypoint,
            )
        )

    def test_rejects_opposite_lane_even_when_trigger_intersects_ego_lane(self) -> None:
        client = CarlaSimulatorClient.__new__(CarlaSimulatorClient)
        ego_waypoint = types.SimpleNamespace(road_id=10, lane_id=1, lane_width=3.5)

        self.assertFalse(
            client._is_stop_sign_for_ego_lane(
                {
                    "road_id": 10,
                    "lane_id": -1,
                    "trigger_min_forward_m": 4.0,
                    "trigger_max_forward_m": 8.0,
                    "trigger_min_abs_lateral_m": 0.4,
                },
                ego_waypoint,
            )
        )

    def test_accepts_stop_sign_when_trigger_intersects_and_lane_metadata_is_missing(self) -> None:
        client = CarlaSimulatorClient.__new__(CarlaSimulatorClient)
        ego_waypoint = types.SimpleNamespace(road_id=10, lane_id=1, lane_width=3.5)

        self.assertTrue(
            client._is_stop_sign_for_ego_lane(
                {
                    "trigger_min_forward_m": 4.0,
                    "trigger_max_forward_m": 8.0,
                    "trigger_min_abs_lateral_m": 0.4,
                },
                ego_waypoint,
            )
        )

    def test_keeps_sign_when_lane_metadata_is_missing(self) -> None:
        client = CarlaSimulatorClient.__new__(CarlaSimulatorClient)
        ego_waypoint = types.SimpleNamespace(road_id=10, lane_id=1, lane_width=3.5)

        self.assertTrue(client._is_stop_sign_for_ego_lane({}, ego_waypoint))


if __name__ == "__main__":
    unittest.main()
