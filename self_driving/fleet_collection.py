from __future__ import annotations

import json
import math
import queue
import time
from contextlib import suppress
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

from self_driving.config import SimulationConfig
from self_driving.data.recording import EpisodeRecorder
from self_driving.networking.messages import FleetMessage
from self_driving.simulator.carla_adapter import normalize_angle_deg
from self_driving.types import ControlCommand, DrivingObservation, Pose2D, VehicleState


class FleetCarlaCollector:
    def __init__(
        self,
        *,
        config: SimulationConfig,
        output_root: str | Path,
        vehicle_count: int,
        spawn_indices: list[int],
        quiet: bool,
        checkpoint_path: str | Path | None = None,
        target_speed_mps: float = 8.0,
        lane_guard: bool = False,
        traffic_rule_guard: bool = False,
    ) -> None:
        self.config = config
        self.output_root = Path(output_root)
        self.vehicle_count = vehicle_count
        self.spawn_indices = spawn_indices
        self.quiet = quiet
        self.checkpoint_path = checkpoint_path
        self.target_speed_mps = target_speed_mps
        self.lane_guard = lane_guard
        self.traffic_rule_guard = traffic_rule_guard
        self._carla: Any = None
        self._client: Any = None
        self._world: Any = None
        self._traffic_manager: Any = None
        self._original_settings: Any = None
        self._traffic_light_actors: list[Any] = []
        self._stop_sign_actors: list[Any] = []
        self._vehicles: list[Any] = []
        self._cameras: list[Any] = []
        self._collision_sensors: list[Any] = []
        self._image_queues: list[queue.Queue[Any]] = []
        self._collision_queues: list[queue.Queue[dict[str, Any]]] = []
        self._recorders: list[EpisodeRecorder] = []
        self._model_controllers: list[Any] = []

    def collect(self) -> dict[str, Any]:
        self._setup()
        frames_recorded = 0
        collision_counts = [0 for _ in self._vehicles]
        total_abs_control_delta = [
            {"throttle": 0.0, "steering": 0.0, "brake": 0.0}
            for _ in self._vehicles
        ]
        max_abs_control_delta = [
            {"throttle": 0.0, "steering": 0.0, "brake": 0.0}
            for _ in self._vehicles
        ]
        try:
            for step in range(self.config.steps):
                self._tick_world()
                observations = [
                    self._capture_observation(index)
                    for index in range(len(self._vehicles))
                ]
                for index, observation in enumerate(observations):
                    if observation.collision_detected:
                        collision_counts[index] += 1
                    message = FleetMessage.from_observation(observation)
                    requested_control = None
                    if self._model_controllers:
                        requested_control = self._model_controllers[index].command(
                            observation,
                            step,
                        )
                        applied_control = observation.state.control
                        deltas = {
                            "throttle": abs(applied_control.throttle - requested_control.throttle),
                            "steering": abs(applied_control.steering - requested_control.steering),
                            "brake": abs(applied_control.brake - requested_control.brake),
                        }
                        for key, value in deltas.items():
                            total_abs_control_delta[index][key] += value
                            max_abs_control_delta[index][key] = max(
                                max_abs_control_delta[index][key],
                                value,
                            )
                    self._recorders[index].record(
                        observation,
                        observation.state.control,
                        message,
                        alerts=[],
                        requested_control=requested_control,
                    )
                frames_recorded += 1
                if not self.quiet and (step == 0 or (step + 1) % 100 == 0):
                    print(
                        json.dumps(
                            {
                                "event": "fleet_collect_progress",
                                "step": step + 1,
                                "steps": self.config.steps,
                                "vehicles": len(self._vehicles),
                            },
                            sort_keys=True,
                        )
                    )
        finally:
            self._teardown()

        summary = {
            "event": "fleet_collection_complete",
            "frames_per_vehicle": frames_recorded,
            "output_root": str(self.output_root),
            "total_frames": frames_recorded * len(collision_counts),
            "vehicle_count": len(collision_counts),
            "vehicle_collision_counts": collision_counts,
            "model_checkpoint": str(self.checkpoint_path) if self.checkpoint_path else None,
            "requested_control_recorded": bool(self._model_controllers),
        }
        if self._model_controllers:
            per_vehicle_average = [
                {
                    key: value / max(frames_recorded, 1)
                    for key, value in vehicle_totals.items()
                }
                for vehicle_totals in total_abs_control_delta
            ]
            summary["per_vehicle_average_abs_control_delta"] = per_vehicle_average
            summary["per_vehicle_max_abs_control_delta"] = max_abs_control_delta
            summary["average_abs_control_delta"] = {
                key: sum(vehicle[key] for vehicle in per_vehicle_average)
                / max(len(per_vehicle_average), 1)
                for key in ("throttle", "steering", "brake")
            }
            summary["max_abs_control_delta"] = {
                key: max(vehicle[key] for vehicle in max_abs_control_delta)
                for key in ("throttle", "steering", "brake")
            }
        self._write_summary(summary)
        return summary

    def _setup(self) -> None:
        try:
            import carla
        except ImportError as exc:
            raise RuntimeError(
                "CARLA Python API is not installed. Install the CARLA Python package "
                "before using the collect-fleet command."
            ) from exc

        self._carla = carla
        self._client = carla.Client(self.config.host, self.config.port)
        self._client.set_timeout(self.config.timeout_seconds)
        self._world = self._client.get_world()
        self._original_settings = self._world.get_settings()
        actors = self._world.get_actors()
        self._traffic_light_actors = list(actors.filter("*traffic_light*"))
        self._stop_sign_actors = list(actors.filter("*stop*"))

        settings = self._world.get_settings()
        settings.synchronous_mode = self.config.synchronous_mode
        settings.fixed_delta_seconds = self.config.fixed_delta_seconds
        self._world.apply_settings(settings)

        self._traffic_manager = self._client.get_trafficmanager(
            self.config.traffic_manager_port
        )
        self._traffic_manager.set_synchronous_mode(self.config.synchronous_mode)

        blueprint_library = self._world.get_blueprint_library()
        vehicle_blueprints = blueprint_library.filter(self.config.vehicle_blueprint)
        if not vehicle_blueprints:
            vehicle_blueprints = blueprint_library.filter("vehicle.*")
        if not vehicle_blueprints:
            raise RuntimeError("No vehicle blueprints are available in the current CARLA world.")

        camera_bp = blueprint_library.find("sensor.camera.rgb")
        camera_bp.set_attribute("image_size_x", str(self.config.camera_width))
        camera_bp.set_attribute("image_size_y", str(self.config.camera_height))
        camera_bp.set_attribute("fov", str(self.config.camera_fov))
        collision_bp = blueprint_library.find("sensor.other.collision")
        controller_cls = None
        if self.checkpoint_path is not None:
            from self_driving.inference import ModelController

            controller_cls = ModelController

        spawn_points = self._world.get_map().get_spawn_points()
        if not spawn_points:
            raise RuntimeError("No spawn points are available in the current CARLA map.")

        self.output_root.mkdir(parents=True, exist_ok=True)
        for index in range(self.vehicle_count):
            spawn_index = self.spawn_indices[index] % len(spawn_points)
            vehicle = None
            for offset in range(len(spawn_points)):
                transform = spawn_points[(spawn_index + offset) % len(spawn_points)]
                blueprint = vehicle_blueprints[index % len(vehicle_blueprints)]
                if blueprint.has_attribute("role_name"):
                    blueprint.set_attribute("role_name", f"fleet-{index + 1:02d}")
                vehicle = self._world.try_spawn_actor(blueprint, transform)
                if vehicle is not None:
                    break
            if vehicle is None:
                raise RuntimeError(f"Failed to spawn fleet vehicle {index + 1}.")

            image_queue: queue.Queue[Any] = queue.Queue()
            collision_queue: queue.Queue[dict[str, Any]] = queue.Queue()
            camera = self._world.spawn_actor(
                camera_bp,
                carla.Transform(carla.Location(x=1.5, z=2.4)),
                attach_to=vehicle,
            )
            camera.listen(image_queue.put)
            collision_sensor = self._world.spawn_actor(
                collision_bp,
                carla.Transform(),
                attach_to=vehicle,
            )
            collision_sensor.listen(
                lambda event, target_queue=collision_queue: self._on_collision(
                    event,
                    target_queue,
                )
            )

            vehicle.set_autopilot(True, self._traffic_manager.get_port())
            config = replace(
                self.config,
                ego_vehicle_id=f"fleet-{index + 1:02d}",
                spawn_index=spawn_index,
            )
            controller_name = "carla_fleet_autopilot"
            if controller_cls is not None:
                controller_name = "carla_fleet_autopilot_guided_model"
                self._model_controllers.append(
                    controller_cls(
                        checkpoint_path=self.checkpoint_path,
                        target_speed_mps=self.target_speed_mps,
                        autopilot_guide=True,
                        lane_guard=self.lane_guard,
                        traffic_rule_guard=self.traffic_rule_guard,
                    )
                )
            recorder = EpisodeRecorder(
                output_dir=self.output_root / f"vehicle_{index + 1:02d}",
                config=config,
                controller_name=controller_name,
            )
            self._vehicles.append(vehicle)
            self._cameras.append(camera)
            self._collision_sensors.append(collision_sensor)
            self._image_queues.append(image_queue)
            self._collision_queues.append(collision_queue)
            self._recorders.append(recorder)

        self._tick_world()

    def _capture_observation(self, index: int) -> DrivingObservation:
        if self._world is None:
            raise RuntimeError("CARLA world is not available.")

        snapshot = self._world.get_snapshot()
        vehicle = self._vehicles[index]
        transform = vehicle.get_transform()
        velocity = vehicle.get_velocity()
        speed_mps = math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2)
        control = vehicle.get_control()
        collision_details = self._drain_collision(index)
        lane_offset_m, heading_error_deg, lane_details = self._lane_metrics(transform)
        traffic_rule_details = self._traffic_rule_details(vehicle, transform)

        state = VehicleState(
            vehicle_id=f"fleet-{index + 1:02d}",
            timestamp=float(snapshot.timestamp.elapsed_seconds),
            pose=Pose2D(
                x=float(transform.location.x),
                y=float(transform.location.y),
                yaw_deg=float(transform.rotation.yaw),
            ),
            speed_mps=float(speed_mps),
            control=ControlCommand(
                throttle=float(control.throttle),
                steering=float(control.steer),
                brake=float(control.brake),
            ),
            frame=int(snapshot.frame),
        )
        return DrivingObservation(
            state=state,
            front_camera_rgb=self._read_camera_image(index, int(snapshot.frame)),
            lane_offset_m=lane_offset_m,
            heading_error_deg=heading_error_deg,
            lane_details=lane_details,
            collision_detected=collision_details is not None,
            collision_details=collision_details,
            traffic_rule_details=traffic_rule_details,
        )

    def _lane_metrics(
        self,
        transform: Any,
    ) -> tuple[float | None, float | None, dict[str, Any] | None]:
        if self._world is None:
            return None, None, None
        waypoint = self._world.get_map().get_waypoint(
            transform.location,
            project_to_road=True,
            lane_type=self._carla.LaneType.Driving,
        )
        if waypoint is None:
            return None, None, None
        waypoint_transform = waypoint.transform
        right = waypoint_transform.get_right_vector()
        delta_x = transform.location.x - waypoint_transform.location.x
        delta_y = transform.location.y - waypoint_transform.location.y
        lateral_offset_m = (delta_x * right.x) + (delta_y * right.y)
        heading_error_deg = normalize_angle_deg(
            transform.rotation.yaw - waypoint_transform.rotation.yaw
        )
        return (
            float(lateral_offset_m),
            float(heading_error_deg),
            {
                "road_id": int(waypoint.road_id),
                "section_id": int(waypoint.section_id),
                "lane_id": int(waypoint.lane_id),
                "lane_width_m": float(waypoint.lane_width),
                "is_junction": bool(waypoint.is_junction),
            },
        )

    def _traffic_rule_details(self, vehicle: Any, transform: Any) -> dict[str, Any] | None:
        traffic_light = self._traffic_light_details(vehicle, transform)
        stop_sign = self._stop_sign_details(transform)
        if traffic_light is None and stop_sign is None:
            return None
        return {
            "traffic_light": traffic_light,
            "stop_sign": stop_sign,
        }

    def _traffic_light_details(self, vehicle: Any, transform: Any) -> dict[str, Any] | None:
        ego_waypoint = None
        with suppress(Exception):
            ego_waypoint = self._world.get_map().get_waypoint(
                transform.location,
                project_to_road=True,
                lane_type=self._carla.LaneType.Driving,
            )

        with suppress(Exception):
            if vehicle.is_at_traffic_light():
                traffic_light = vehicle.get_traffic_light()
                if traffic_light is not None:
                    details = self._traffic_actor_details(
                        traffic_light,
                        transform,
                        state=str(vehicle.get_traffic_light_state()).split(".")[-1],
                    )
                    if details is not None:
                        details["source"] = "vehicle_traffic_light"
                    return details

        best: dict[str, Any] | None = None
        for traffic_light in self._traffic_light_actors:
            with suppress(Exception):
                state = str(traffic_light.state).split(".")[-1]
                if state not in {"Red", "Yellow", "Green"}:
                    continue
                details = self._traffic_actor_details(traffic_light, transform, state=state)
                if details is None:
                    continue
                if not self._traffic_light_geometry_matches_ego_lane(details, ego_waypoint):
                    continue
                if not self._traffic_light_candidate_in_range(details):
                    continue
                details["source"] = "fallback_traffic_light_scan"
                if best is None or self._traffic_light_sort_key(details) < self._traffic_light_sort_key(best):
                    best = details
        return best

    def _traffic_light_geometry_matches_ego_lane(
        self,
        details: dict[str, Any],
        ego_waypoint: Any | None,
    ) -> bool:
        if ego_waypoint is not None and self._traffic_light_trigger_intersects_ego_lane(
            details,
            ego_waypoint,
        ):
            light_road_id = details.get("road_id")
            light_lane_id = details.get("lane_id")
            if (
                light_road_id is not None
                and int(light_road_id) == int(ego_waypoint.road_id)
                and light_lane_id is not None
            ):
                return int(light_lane_id) == int(ego_waypoint.lane_id)
            if bool(getattr(ego_waypoint, "is_junction", False)):
                return False
            return True

        if ego_waypoint is not None and self._traffic_light_lane_matches_ego_lane(
            details,
            ego_waypoint,
        ):
            return abs(details["lateral_distance_m"]) <= 6.0 and abs(details["angle_deg"]) <= 70.0

        return abs(details["lateral_distance_m"]) <= 3.4 and abs(details["angle_deg"]) <= 45.0

    def _traffic_light_lane_matches_ego_lane(self, details: dict[str, Any], ego_waypoint: Any) -> bool:
        light_road_id = details.get("road_id")
        light_lane_id = details.get("lane_id")
        if light_road_id is None or light_lane_id is None:
            return False
        return (
            int(light_road_id) == int(ego_waypoint.road_id)
            and int(light_lane_id) == int(ego_waypoint.lane_id)
        )

    def _traffic_light_trigger_intersects_ego_lane(
        self,
        details: dict[str, Any],
        ego_waypoint: Any,
    ) -> bool:
        min_forward = details.get("trigger_min_forward_m")
        max_forward = details.get("trigger_max_forward_m")
        min_abs_lateral = details.get("trigger_min_abs_lateral_m")
        if min_forward is None or max_forward is None or min_abs_lateral is None:
            return False

        lane_width = float(getattr(ego_waypoint, "lane_width", 3.5) or 3.5)
        lane_corridor_half_width = (lane_width * 0.5) + 0.45
        return (
            float(max_forward) >= -2.0
            and float(min_forward) <= 24.0
            and float(min_abs_lateral) <= lane_corridor_half_width
        )

    def _traffic_light_candidate_in_range(self, details: dict[str, Any]) -> bool:
        min_forward = details.get("trigger_min_forward_m")
        max_forward = details.get("trigger_max_forward_m")
        if min_forward is not None and max_forward is not None:
            return float(max_forward) >= -2.0 and float(min_forward) <= 24.0
        return (
            0.0 <= details["forward_distance_m"] <= 14.0
            and abs(details["lateral_distance_m"]) <= 5.0
            and abs(details["angle_deg"]) <= 60.0
        )

    def _traffic_light_sort_key(self, details: dict[str, Any]) -> tuple[float, float, float]:
        forward = float(details.get("trigger_min_forward_m", details["forward_distance_m"]))
        lateral = float(details.get("trigger_min_abs_lateral_m", abs(details["lateral_distance_m"])))
        return (max(forward, -2.0), lateral, float(details["distance_m"]))

    def _stop_sign_details(self, transform: Any) -> dict[str, Any] | None:
        ego_waypoint = None
        with suppress(Exception):
            ego_waypoint = self._world.get_map().get_waypoint(
                transform.location,
                project_to_road=True,
                lane_type=self._carla.LaneType.Driving,
            )

        best: dict[str, Any] | None = None
        for stop_sign in self._stop_sign_actors:
            details = self._traffic_actor_details(stop_sign, transform, state="Stop")
            if details is None:
                continue
            if ego_waypoint is not None and not self._is_stop_sign_for_ego_lane(
                details,
                ego_waypoint,
            ):
                continue
            if (
                -8.0 <= details["forward_distance_m"] <= 18.0
                and self._stop_sign_geometry_matches_ego_lane(details, ego_waypoint)
                and (
                    best is None
                    or details["forward_distance_m"] < best["forward_distance_m"]
                )
            ):
                details["source"] = "fallback_stop_sign_scan"
                best = details
        return best

    def _is_stop_sign_for_ego_lane(self, details: dict[str, Any], ego_waypoint: Any) -> bool:
        sign_road_id = details.get("road_id")
        sign_lane_id = details.get("lane_id")
        if self._stop_sign_trigger_intersects_ego_lane(details, ego_waypoint):
            if (
                sign_road_id is not None
                and int(sign_road_id) == int(ego_waypoint.road_id)
                and sign_lane_id is not None
            ):
                return int(sign_lane_id) == int(ego_waypoint.lane_id)
            return self._stop_sign_trigger_matches_ego_approach(details, ego_waypoint)

        if sign_road_id is not None and sign_lane_id is not None:
            return self._stop_sign_lane_matches_ego_lane(details, ego_waypoint)

        return sign_road_id is None and sign_lane_id is None

    def _stop_sign_lane_matches_ego_lane(self, details: dict[str, Any], ego_waypoint: Any) -> bool:
        sign_road_id = details.get("road_id")
        sign_lane_id = details.get("lane_id")
        if sign_road_id is None or sign_lane_id is None:
            return False
        return (
            int(sign_road_id) == int(ego_waypoint.road_id)
            and int(sign_lane_id) == int(ego_waypoint.lane_id)
        )

    def _stop_sign_geometry_matches_ego_lane(
        self,
        details: dict[str, Any],
        ego_waypoint: Any | None,
    ) -> bool:
        if ego_waypoint is not None and self._stop_sign_trigger_intersects_ego_lane(
            details,
            ego_waypoint,
        ):
            if self._stop_sign_lane_matches_ego_lane(details, ego_waypoint):
                return True
            return self._stop_sign_trigger_matches_ego_approach(details, ego_waypoint)
        if ego_waypoint is not None and self._stop_sign_lane_matches_ego_lane(
            details,
            ego_waypoint,
        ):
            return abs(details["lateral_distance_m"]) <= 6.0

        return abs(details["lateral_distance_m"]) <= 3.4 and abs(details["angle_deg"]) <= 45.0

    def _stop_sign_trigger_matches_ego_approach(
        self,
        details: dict[str, Any],
        ego_waypoint: Any,
    ) -> bool:
        lane_width = float(getattr(ego_waypoint, "lane_width", 3.5) or 3.5)
        lateral_limit = (lane_width * 0.5) + 0.75
        return (
            abs(float(details.get("lateral_distance_m", 999.0))) <= lateral_limit
            and abs(float(details.get("angle_deg", 999.0))) <= 45.0
        )

    def _stop_sign_trigger_intersects_ego_lane(
        self,
        details: dict[str, Any],
        ego_waypoint: Any,
    ) -> bool:
        min_forward = details.get("trigger_min_forward_m")
        max_forward = details.get("trigger_max_forward_m")
        min_abs_lateral = details.get("trigger_min_abs_lateral_m")
        if min_forward is None or max_forward is None or min_abs_lateral is None:
            return False

        lane_width = float(getattr(ego_waypoint, "lane_width", 3.5) or 3.5)
        lane_corridor_half_width = (lane_width * 0.5) + 0.45
        return (
            float(max_forward) >= -8.0
            and float(min_forward) <= 18.0
            and float(min_abs_lateral) <= lane_corridor_half_width
        )

    def _traffic_actor_details(
        self,
        actor: Any,
        ego_transform: Any,
        *,
        state: str,
    ) -> dict[str, Any] | None:
        try:
            actor_location = self._traffic_actor_location(actor)
            forward = ego_transform.get_forward_vector()
            right = ego_transform.get_right_vector()
            delta_x = actor_location.x - ego_transform.location.x
            delta_y = actor_location.y - ego_transform.location.y
            distance_m = math.sqrt(delta_x**2 + delta_y**2)
            forward_distance_m = (delta_x * forward.x) + (delta_y * forward.y)
            lateral_distance_m = (delta_x * right.x) + (delta_y * right.y)
            angle_deg = math.degrees(
                math.atan2(lateral_distance_m, max(forward_distance_m, 0.001))
            )
            waypoint = self._world.get_map().get_waypoint(
                actor_location,
                project_to_road=True,
                lane_type=self._carla.LaneType.Driving,
            )
            trigger_metrics = self._traffic_actor_trigger_metrics(actor, ego_transform)
        except Exception:
            return None

        details = {
            "id": int(actor.id),
            "type_id": str(actor.type_id),
            "state": state,
            "distance_m": float(distance_m),
            "forward_distance_m": float(forward_distance_m),
            "lateral_distance_m": float(lateral_distance_m),
            "angle_deg": float(angle_deg),
        }
        if trigger_metrics is not None:
            details.update(trigger_metrics)
        if waypoint is not None:
            details.update(
                {
                    "road_id": int(waypoint.road_id),
                    "section_id": int(waypoint.section_id),
                    "lane_id": int(waypoint.lane_id),
                    "is_junction": bool(waypoint.is_junction),
                }
            )
        return details

    def _traffic_actor_trigger_metrics(
        self,
        actor: Any,
        ego_transform: Any,
    ) -> dict[str, float] | None:
        trigger_volume = getattr(actor, "trigger_volume", None)
        if trigger_volume is None:
            return None

        actor_transform = actor.get_transform()
        center = trigger_volume.location
        extent = trigger_volume.extent
        local_points = [
            self._carla.Location(x=center.x, y=center.y, z=center.z),
            self._carla.Location(x=center.x + extent.x, y=center.y + extent.y, z=center.z),
            self._carla.Location(x=center.x + extent.x, y=center.y - extent.y, z=center.z),
            self._carla.Location(x=center.x - extent.x, y=center.y + extent.y, z=center.z),
            self._carla.Location(x=center.x - extent.x, y=center.y - extent.y, z=center.z),
        ]
        forward = ego_transform.get_forward_vector()
        right = ego_transform.get_right_vector()
        forward_distances = []
        lateral_distances = []
        for local_point in local_points:
            world_point = actor_transform.transform(local_point)
            delta_x = world_point.x - ego_transform.location.x
            delta_y = world_point.y - ego_transform.location.y
            forward_distances.append((delta_x * forward.x) + (delta_y * forward.y))
            lateral_distances.append((delta_x * right.x) + (delta_y * right.y))

        return {
            "trigger_min_forward_m": float(min(forward_distances)),
            "trigger_max_forward_m": float(max(forward_distances)),
            "trigger_min_abs_lateral_m": float(min(abs(value) for value in lateral_distances)),
            "trigger_max_abs_lateral_m": float(max(abs(value) for value in lateral_distances)),
        }

    def _traffic_actor_location(self, actor: Any) -> Any:
        transform = actor.get_transform()
        trigger_volume = getattr(actor, "trigger_volume", None)
        if trigger_volume is None:
            return transform.location
        return transform.transform(trigger_volume.location)

    def _read_camera_image(self, index: int, target_frame: int) -> np.ndarray:
        deadline = time.monotonic() + self.config.timeout_seconds
        image = None
        while time.monotonic() < deadline:
            timeout = max(0.01, deadline - time.monotonic())
            try:
                candidate = self._image_queues[index].get(timeout=timeout)
            except queue.Empty as exc:
                raise RuntimeError("Timed out waiting for CARLA camera frames.") from exc
            image = candidate
            if getattr(candidate, "frame", -1) >= target_frame:
                break
        if image is None:
            raise RuntimeError("No CARLA camera frame was received.")
        array = np.frombuffer(image.raw_data, dtype=np.uint8)
        array = array.reshape((image.height, image.width, 4))
        return array[:, :, :3][:, :, ::-1].copy()

    def _drain_collision(self, index: int) -> dict[str, Any] | None:
        last_event = None
        while True:
            try:
                last_event = self._collision_queues[index].get_nowait()
            except queue.Empty:
                return last_event

    def _on_collision(self, event: Any, target_queue: queue.Queue[dict[str, Any]]) -> None:
        impulse = event.normal_impulse
        target_queue.put(
            {
                "frame": int(event.frame),
                "impulse_magnitude": float(
                    math.sqrt(impulse.x**2 + impulse.y**2 + impulse.z**2)
                ),
                "normal_impulse": {
                    "x": float(impulse.x),
                    "y": float(impulse.y),
                    "z": float(impulse.z),
                },
                "other_actor": {
                    "id": int(event.other_actor.id),
                    "type_id": str(event.other_actor.type_id),
                },
            }
        )

    def _tick_world(self) -> None:
        if self._world is None:
            raise RuntimeError("CARLA world is not available.")
        if self.config.synchronous_mode:
            self._world.tick()
        else:
            self._world.wait_for_tick()

    def _teardown(self) -> None:
        for recorder in self._recorders:
            with suppress(Exception):
                recorder.close()
        if self._traffic_manager is not None:
            with suppress(Exception):
                self._traffic_manager.set_synchronous_mode(False)
        for vehicle in self._vehicles:
            with suppress(Exception):
                vehicle.set_autopilot(False, self._traffic_manager.get_port())
        for actor in [*self._cameras, *self._collision_sensors, *self._vehicles]:
            with suppress(Exception):
                if hasattr(actor, "stop"):
                    actor.stop()
            with suppress(Exception):
                actor.destroy()
        if self._world is not None and self._original_settings is not None:
            with suppress(Exception):
                self._world.apply_settings(self._original_settings)

    def _write_summary(self, summary: dict[str, Any]) -> None:
        with suppress(Exception):
            self.output_root.mkdir(parents=True, exist_ok=True)
            summary_path = self.output_root / "fleet_summary.json"
            summary_path.write_text(
                json.dumps(summary, indent=2, sort_keys=True),
                encoding="utf-8",
            )


def collect_carla_fleet(
    *,
    config: SimulationConfig,
    output_root: str | Path,
    vehicle_count: int,
    spawn_indices: list[int],
    quiet: bool,
    checkpoint_path: str | Path | None = None,
    target_speed_mps: float = 8.0,
    lane_guard: bool = False,
    traffic_rule_guard: bool = False,
) -> dict[str, Any]:
    if vehicle_count < 1:
        raise ValueError("vehicle_count must be at least 1.")
    if vehicle_count > 10:
        raise ValueError("vehicle_count is capped at 10 to keep camera recording manageable.")
    if len(spawn_indices) < vehicle_count:
        spawn_indices = [*spawn_indices, *range(len(spawn_indices), vehicle_count)]
    root = Path(output_root)
    if root.exists():
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        root = root.with_name(f"{root.name}_{stamp}")

    collector = FleetCarlaCollector(
        config=config,
        output_root=root,
        vehicle_count=vehicle_count,
        spawn_indices=spawn_indices,
        quiet=quiet,
        checkpoint_path=checkpoint_path,
        target_speed_mps=target_speed_mps,
        lane_guard=lane_guard,
        traffic_rule_guard=traffic_rule_guard,
    )
    return collector.collect()
