from __future__ import annotations

import types
import unittest
import sys

cv2_stub = types.ModuleType("cv2")
sys.modules.setdefault("cv2", cv2_stub)

from self_driving.fleet_collection import FleetCarlaCollector
from self_driving.simulator.carla_adapter import CarlaSimulatorClient


class CarlaStopSignFilterTests(unittest.TestCase):
    def test_rejects_traffic_light_on_opposite_lane(self) -> None:
        client = CarlaSimulatorClient.__new__(CarlaSimulatorClient)
        ego_waypoint = types.SimpleNamespace(road_id=21, lane_id=-2, lane_width=3.5)

        self.assertFalse(
            client._traffic_light_geometry_matches_ego_lane(
                {
                    "road_id": 21,
                    "lane_id": 2,
                    "trigger_min_forward_m": 2.0,
                    "trigger_max_forward_m": 4.0,
                    "trigger_min_abs_lateral_m": 0.5,
                    "lateral_distance_m": 0.5,
                    "angle_deg": 4.0,
                },
                ego_waypoint,
            )
        )

    def test_accepts_same_lane_traffic_light_trigger(self) -> None:
        client = CarlaSimulatorClient.__new__(CarlaSimulatorClient)
        ego_waypoint = types.SimpleNamespace(road_id=21, lane_id=-2, lane_width=3.5)

        self.assertTrue(
            client._traffic_light_geometry_matches_ego_lane(
                {
                    "road_id": 21,
                    "lane_id": -2,
                    "trigger_min_forward_m": 2.0,
                    "trigger_max_forward_m": 4.0,
                    "trigger_min_abs_lateral_m": 0.5,
                    "lateral_distance_m": 0.5,
                    "angle_deg": 4.0,
                },
                ego_waypoint,
            )
        )

    def test_accepts_intersection_traffic_light_when_trigger_intersects(self) -> None:
        client = CarlaSimulatorClient.__new__(CarlaSimulatorClient)
        ego_waypoint = types.SimpleNamespace(road_id=21, lane_id=-2, lane_width=3.5)

        self.assertTrue(
            client._traffic_light_geometry_matches_ego_lane(
                {
                    "road_id": 150,
                    "lane_id": -2,
                    "trigger_min_forward_m": 2.0,
                    "trigger_max_forward_m": 4.0,
                    "trigger_min_abs_lateral_m": 0.5,
                    "lateral_distance_m": 0.5,
                    "angle_deg": 4.0,
                },
                ego_waypoint,
            )
        )

    def test_rejects_cross_road_traffic_light_while_inside_junction(self) -> None:
        client = CarlaSimulatorClient.__new__(CarlaSimulatorClient)
        ego_waypoint = types.SimpleNamespace(
            road_id=255,
            lane_id=-1,
            lane_width=3.5,
            is_junction=True,
        )

        self.assertFalse(
            client._traffic_light_geometry_matches_ego_lane(
                {
                    "road_id": 20,
                    "lane_id": 5,
                    "trigger_min_forward_m": 15.18,
                    "trigger_max_forward_m": 19.71,
                    "trigger_min_abs_lateral_m": 0.4,
                    "lateral_distance_m": 0.4,
                    "angle_deg": 1.3,
                },
                ego_waypoint,
            )
        )

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

    def test_accepts_intersection_stop_sign_when_trigger_intersects_ego_lane(self) -> None:
        client = CarlaSimulatorClient.__new__(CarlaSimulatorClient)
        ego_waypoint = types.SimpleNamespace(road_id=12, lane_id=1, lane_width=3.5)

        self.assertTrue(
            client._is_stop_sign_for_ego_lane(
                {
                    "road_id": 150,
                    "lane_id": 1,
                    "trigger_min_forward_m": 12.89,
                    "trigger_max_forward_m": 14.95,
                    "trigger_min_abs_lateral_m": 0.2,
                    "lateral_distance_m": 0.2,
                    "angle_deg": 1.0,
                },
                ego_waypoint,
            )
        )

    def test_rejects_intersection_stop_sign_on_cross_approach(self) -> None:
        client = CarlaSimulatorClient.__new__(CarlaSimulatorClient)
        ego_waypoint = types.SimpleNamespace(road_id=12, lane_id=1, lane_width=3.5)

        self.assertFalse(
            client._is_stop_sign_for_ego_lane(
                {
                    "road_id": 150,
                    "lane_id": 1,
                    "trigger_min_forward_m": 5.0,
                    "trigger_max_forward_m": 9.0,
                    "trigger_min_abs_lateral_m": 0.2,
                    "lateral_distance_m": 3.2,
                    "angle_deg": 58.0,
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
                    "lateral_distance_m": 0.4,
                    "angle_deg": 4.0,
                },
                ego_waypoint,
            )
        )

    def test_accepts_same_lane_sign_after_passing_actor_center(self) -> None:
        client = CarlaSimulatorClient.__new__(CarlaSimulatorClient)
        ego_waypoint = types.SimpleNamespace(road_id=10, lane_id=1, lane_width=3.5)

        self.assertTrue(
            client._stop_sign_geometry_matches_ego_lane(
                {
                    "road_id": 10,
                    "lane_id": 1,
                    "forward_distance_m": -3.0,
                    "lateral_distance_m": 4.5,
                    "angle_deg": 88.0,
                },
                ego_waypoint,
            )
        )

    def test_keeps_sign_when_lane_metadata_is_missing(self) -> None:
        client = CarlaSimulatorClient.__new__(CarlaSimulatorClient)
        ego_waypoint = types.SimpleNamespace(road_id=10, lane_id=1, lane_width=3.5)

        self.assertTrue(client._is_stop_sign_for_ego_lane({}, ego_waypoint))


class FleetStopSignFilterTests(unittest.TestCase):
    def test_rejects_traffic_light_on_opposite_lane(self) -> None:
        collector = FleetCarlaCollector.__new__(FleetCarlaCollector)
        ego_waypoint = types.SimpleNamespace(road_id=21, lane_id=-2, lane_width=3.5)

        self.assertFalse(
            collector._traffic_light_geometry_matches_ego_lane(
                {
                    "road_id": 21,
                    "lane_id": 2,
                    "trigger_min_forward_m": 2.0,
                    "trigger_max_forward_m": 4.0,
                    "trigger_min_abs_lateral_m": 0.5,
                    "lateral_distance_m": 0.5,
                    "angle_deg": 4.0,
                },
                ego_waypoint,
            )
        )

    def test_accepts_same_lane_traffic_light_trigger(self) -> None:
        collector = FleetCarlaCollector.__new__(FleetCarlaCollector)
        ego_waypoint = types.SimpleNamespace(road_id=21, lane_id=-2, lane_width=3.5)

        self.assertTrue(
            collector._traffic_light_geometry_matches_ego_lane(
                {
                    "road_id": 21,
                    "lane_id": -2,
                    "trigger_min_forward_m": 2.0,
                    "trigger_max_forward_m": 4.0,
                    "trigger_min_abs_lateral_m": 0.5,
                    "lateral_distance_m": 0.5,
                    "angle_deg": 4.0,
                },
                ego_waypoint,
            )
        )

    def test_rejects_cross_road_traffic_light_while_inside_junction(self) -> None:
        collector = FleetCarlaCollector.__new__(FleetCarlaCollector)
        ego_waypoint = types.SimpleNamespace(
            road_id=255,
            lane_id=-1,
            lane_width=3.5,
            is_junction=True,
        )

        self.assertFalse(
            collector._traffic_light_geometry_matches_ego_lane(
                {
                    "road_id": 20,
                    "lane_id": 5,
                    "trigger_min_forward_m": 15.18,
                    "trigger_max_forward_m": 19.71,
                    "trigger_min_abs_lateral_m": 0.4,
                    "lateral_distance_m": 0.4,
                    "angle_deg": 1.3,
                },
                ego_waypoint,
            )
        )

    def test_rejects_stop_sign_on_opposite_lane(self) -> None:
        collector = FleetCarlaCollector.__new__(FleetCarlaCollector)
        ego_waypoint = types.SimpleNamespace(road_id=10, lane_id=1)

        self.assertFalse(
            collector._is_stop_sign_for_ego_lane(
                {"road_id": 10, "lane_id": -1},
                ego_waypoint,
            )
        )

    def test_rejects_opposite_lane_even_when_trigger_intersects_ego_lane(self) -> None:
        collector = FleetCarlaCollector.__new__(FleetCarlaCollector)
        ego_waypoint = types.SimpleNamespace(road_id=10, lane_id=1, lane_width=3.5)

        self.assertFalse(
            collector._is_stop_sign_for_ego_lane(
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

    def test_accepts_intersection_stop_sign_when_trigger_intersects_ego_lane(self) -> None:
        collector = FleetCarlaCollector.__new__(FleetCarlaCollector)
        ego_waypoint = types.SimpleNamespace(road_id=12, lane_id=1, lane_width=3.5)

        self.assertTrue(
            collector._is_stop_sign_for_ego_lane(
                {
                    "road_id": 150,
                    "lane_id": 1,
                    "trigger_min_forward_m": 12.89,
                    "trigger_max_forward_m": 14.95,
                    "trigger_min_abs_lateral_m": 0.2,
                    "lateral_distance_m": 0.2,
                    "angle_deg": 1.0,
                },
                ego_waypoint,
            )
        )

    def test_rejects_intersection_stop_sign_on_cross_approach(self) -> None:
        collector = FleetCarlaCollector.__new__(FleetCarlaCollector)
        ego_waypoint = types.SimpleNamespace(road_id=12, lane_id=1, lane_width=3.5)

        self.assertFalse(
            collector._is_stop_sign_for_ego_lane(
                {
                    "road_id": 150,
                    "lane_id": 1,
                    "trigger_min_forward_m": 5.0,
                    "trigger_max_forward_m": 9.0,
                    "trigger_min_abs_lateral_m": 0.2,
                    "lateral_distance_m": 3.2,
                    "angle_deg": 58.0,
                },
                ego_waypoint,
            )
        )

    def test_accepts_same_lane_sign_after_passing_actor_center(self) -> None:
        collector = FleetCarlaCollector.__new__(FleetCarlaCollector)
        ego_waypoint = types.SimpleNamespace(road_id=10, lane_id=1, lane_width=3.5)

        self.assertTrue(
            collector._stop_sign_geometry_matches_ego_lane(
                {
                    "road_id": 10,
                    "lane_id": 1,
                    "forward_distance_m": -3.0,
                    "lateral_distance_m": 4.5,
                    "angle_deg": 88.0,
                },
                ego_waypoint,
            )
        )


if __name__ == "__main__":
    unittest.main()
