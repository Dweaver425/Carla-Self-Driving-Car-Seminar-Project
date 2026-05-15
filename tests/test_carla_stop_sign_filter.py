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
        ego_waypoint = types.SimpleNamespace(road_id=10, lane_id=1)

        self.assertTrue(
            client._is_stop_sign_for_ego_lane(
                {"road_id": 10, "lane_id": 1},
                ego_waypoint,
            )
        )

    def test_keeps_sign_when_lane_metadata_is_missing(self) -> None:
        client = CarlaSimulatorClient.__new__(CarlaSimulatorClient)
        ego_waypoint = types.SimpleNamespace(road_id=10, lane_id=1)

        self.assertTrue(client._is_stop_sign_for_ego_lane({}, ego_waypoint))


if __name__ == "__main__":
    unittest.main()
