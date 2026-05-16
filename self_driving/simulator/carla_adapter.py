from __future__ import annotations

import math
import queue
import time
from contextlib import suppress
from typing import Any

import numpy as np

from self_driving.config import SimulationConfig
from self_driving.simulator.base import SimulatorClient
from self_driving.types import ControlCommand, DrivingObservation, Pose2D, VehicleState


class CarlaSimulatorClient(SimulatorClient):
    def __init__(self, config: SimulationConfig) -> None:
        self.config = config
        self._carla: Any = None
        self._client: Any = None
        self._traffic_manager: Any = None
        self._world: Any = None
        self._vehicle: Any = None
        self._camera: Any = None
        self._collision_sensor: Any = None
        self._obstacle_sensor: Any = None
        self._traffic_light_actors: list[Any] = []
        self._stop_sign_actors: list[Any] = []
        self._image_queue: queue.Queue[Any] = queue.Queue()
        self._collision_events: queue.Queue[dict[str, Any]] = queue.Queue()
        self._pending_collision_events: list[dict[str, Any]] = []
        self._obstacle_events: queue.Queue[dict[str, Any]] = queue.Queue()
        self._pending_obstacle_events: list[dict[str, Any]] = []
        self._original_settings: Any = None
        self._autopilot_enabled = False
        self._last_command = ControlCommand()
        self._closed = False

    def setup(self) -> None:
        try:
            import carla
        except ImportError as exc:
            raise RuntimeError(
                "CARLA Python API is not installed. Install the CARLA Python package "
                "in this environment before using '--backend carla'."
            ) from exc

        self._carla = carla
        self._client = carla.Client(self.config.host, self.config.port)
        self._client.set_timeout(self.config.timeout_seconds)
        self._world = self._client.get_world()
        self._original_settings = self._world.get_settings()
        actors = self._world.get_actors()
        self._traffic_light_actors = list(actors.filter("*traffic_light*"))
        self._stop_sign_actors = list(actors.filter("*stop*"))

        if self.config.synchronous_mode:
            settings = self._world.get_settings()
            # Step CARLA in lockstep so vehicle state and sensor frames stay deterministic.
            settings.synchronous_mode = True
            settings.fixed_delta_seconds = self.config.fixed_delta_seconds
            self._world.apply_settings(settings)

        blueprint_library = self._world.get_blueprint_library()
        blueprints = blueprint_library.filter(self.config.vehicle_blueprint)
        if not blueprints:
            blueprints = blueprint_library.filter("vehicle.*")
        if not blueprints:
            raise RuntimeError("No vehicle blueprints are available in the current CARLA world.")

        blueprint = blueprints[0]
        if blueprint.has_attribute("role_name"):
            blueprint.set_attribute("role_name", self.config.ego_vehicle_id)

        spawn_points = self._world.get_map().get_spawn_points()
        if not spawn_points:
            raise RuntimeError("No spawn points are available in the current CARLA map.")

        # Try the requested spawn point first, then fall back across the rest of the map.
        # This keeps long unattended runs alive when traffic happens to occupy one location.
        start_index = self.config.spawn_index % len(spawn_points)
        for offset in range(len(spawn_points)):
            transform = self._adjust_spawn_transform(
                spawn_points[(start_index + offset) % len(spawn_points)]
            )
            self._vehicle = self._world.try_spawn_actor(blueprint, transform)
            if self._vehicle is not None:
                break

        if self._vehicle is None:
            raise RuntimeError(
                "Failed to spawn the ego vehicle after trying all available spawn points. "
                "Reduce traffic density or clear the world and try again."
            )

        camera_bp = blueprint_library.find("sensor.camera.rgb")
        camera_bp.set_attribute("image_size_x", str(self.config.camera_width))
        camera_bp.set_attribute("image_size_y", str(self.config.camera_height))
        camera_bp.set_attribute("fov", str(self.config.camera_fov))
        camera_transform = carla.Transform(carla.Location(x=1.5, z=2.4))
        self._camera = self._world.spawn_actor(camera_bp, camera_transform, attach_to=self._vehicle)
        self._camera.listen(self._image_queue.put)

        collision_bp = blueprint_library.find("sensor.other.collision")
        self._collision_sensor = self._world.spawn_actor(
            collision_bp,
            carla.Transform(),
            attach_to=self._vehicle,
        )
        self._collision_sensor.listen(self._on_collision)

        obstacle_bp = blueprint_library.find("sensor.other.obstacle")
        if obstacle_bp.has_attribute("distance"):
            obstacle_bp.set_attribute("distance", "8.0")
        if obstacle_bp.has_attribute("hit_radius"):
            obstacle_bp.set_attribute("hit_radius", "0.75")
        if obstacle_bp.has_attribute("only_dynamics"):
            obstacle_bp.set_attribute("only_dynamics", "false")
        obstacle_transform = carla.Transform(carla.Location(x=2.5, z=1.2))
        self._obstacle_sensor = self._world.spawn_actor(
            obstacle_bp,
            obstacle_transform,
            attach_to=self._vehicle,
        )
        self._obstacle_sensor.listen(self._on_obstacle)

        self._tick_world()

    def enable_autopilot(self) -> None:
        if self._client is None or self._vehicle is None:
            raise RuntimeError("CARLA backend is not initialized.")

        self._traffic_manager = self._client.get_trafficmanager(self.config.traffic_manager_port)
        self._traffic_manager.set_synchronous_mode(self.config.synchronous_mode)
        self._vehicle.set_autopilot(True, self._traffic_manager.get_port())
        self._autopilot_enabled = True
        # Let Traffic Manager apply its first control before we start recording.
        self._tick_world()

    def get_observation(self) -> DrivingObservation:
        return self._capture_observation()

    def step(self, command: ControlCommand) -> DrivingObservation:
        if self._vehicle is None or self._world is None or self._carla is None:
            raise RuntimeError("CARLA backend is not initialized.")

        if not self._autopilot_enabled:
            self._vehicle.apply_control(
                self._carla.VehicleControl(
                    throttle=float(command.throttle),
                    steer=float(command.steering),
                    brake=float(command.brake),
                )
            )
        self._tick_world()
        return self._capture_observation()

    def teardown(self) -> None:
        if self._closed:
            return
        self._closed = True

        if self._vehicle is not None and self._autopilot_enabled and self._traffic_manager is not None:
            # CARLA can destroy actors during shutdown; treat teardown as best-effort cleanup.
            with suppress(Exception):
                self._vehicle.set_autopilot(False, self._traffic_manager.get_port())
            self._autopilot_enabled = False
            self._teardown_tick()

        sensor_names = ("_camera", "_collision_sensor", "_obstacle_sensor")
        for actor_name in sensor_names:
            self._stop_actor_listener(getattr(self, actor_name))
        self._teardown_tick()

        for actor_name in sensor_names:
            self._destroy_actor(actor_name)
        self._teardown_tick()

        self._destroy_actor("_vehicle")

        if self._traffic_manager is not None and self.config.synchronous_mode:
            with suppress(Exception):
                self._traffic_manager.set_synchronous_mode(False)
            self._traffic_manager = None

        if self._world is not None and self._original_settings is not None:
            with suppress(Exception):
                self._world.apply_settings(self._original_settings)
            self._original_settings = None

        self._clear_queues()

    def _stop_actor_listener(self, actor: Any) -> None:
        if actor is None or not hasattr(actor, "stop"):
            return
        with suppress(Exception):
            actor.stop()

    def _destroy_actor(self, actor_name: str) -> None:
        actor = getattr(self, actor_name)
        if actor is None:
            return
        with suppress(Exception):
            if hasattr(actor, "is_alive") and not actor.is_alive:
                return
            actor.destroy()
        setattr(self, actor_name, None)

    def _teardown_tick(self) -> None:
        if self._world is None:
            return
        with suppress(Exception):
            if self.config.synchronous_mode:
                self._world.tick()
            else:
                self._world.wait_for_tick()

    def _clear_queues(self) -> None:
        self._pending_collision_events.clear()
        self._pending_obstacle_events.clear()
        for event_queue in (self._image_queue, self._collision_events, self._obstacle_events):
            while True:
                try:
                    event_queue.get_nowait()
                except queue.Empty:
                    break

    def _tick_world(self) -> None:
        if self._world is None:
            raise RuntimeError("CARLA world is not available.")
        if self.config.synchronous_mode:
            self._world.tick()
        else:
            self._world.wait_for_tick()
        self._update_spectator()

    def _update_spectator(self) -> None:
        if (
            self.config.spectator_mode == "none"
            or self._world is None
            or self._vehicle is None
            or self._carla is None
        ):
            return

        transform = self._vehicle.get_transform()
        rotation = transform.rotation
        forward = transform.get_forward_vector()

        if self.config.spectator_mode == "hood":
            location = self._carla.Location(
                x=transform.location.x + forward.x * 1.5,
                y=transform.location.y + forward.y * 1.5,
                z=transform.location.z + 2.35,
            )
            spectator_rotation = self._carla.Rotation(
                pitch=rotation.pitch - 5.0,
                yaw=rotation.yaw,
                roll=0.0,
            )
        else:
            location = self._carla.Location(
                x=transform.location.x - forward.x * 8.0,
                y=transform.location.y - forward.y * 8.0,
                z=transform.location.z + 4.0,
            )
            spectator_rotation = self._carla.Rotation(
                pitch=-12.0,
                yaw=rotation.yaw,
                roll=0.0,
            )

        self._world.get_spectator().set_transform(
            self._carla.Transform(location, spectator_rotation)
        )

    def _capture_observation(self) -> DrivingObservation:
        if self._vehicle is None or self._world is None:
            raise RuntimeError("CARLA backend is not initialized.")

        snapshot = self._world.get_snapshot()
        transform = self._vehicle.get_transform()
        velocity = self._vehicle.get_velocity()
        speed_mps = math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2)
        image_rgb = self._read_camera_image(snapshot.frame)
        vehicle_control = self._vehicle.get_control()
        lane_offset_m, heading_error_deg, lane_details = self._lane_metrics(transform)
        applied_command = ControlCommand(
            throttle=float(vehicle_control.throttle),
            steering=float(vehicle_control.steer),
            brake=float(vehicle_control.brake),
        )
        self._last_command = applied_command

        state = VehicleState(
            vehicle_id=self.config.ego_vehicle_id,
            timestamp=snapshot.timestamp.elapsed_seconds,
            pose=Pose2D(
                x=transform.location.x,
                y=transform.location.y,
                yaw_deg=transform.rotation.yaw,
            ),
            speed_mps=speed_mps,
            control=applied_command,
            frame=snapshot.frame,
        )
        collision_details = self._consume_collision_details(snapshot.frame)
        obstacle_details = self._consume_obstacle_details(snapshot.frame)
        traffic_rule_details = self._traffic_rule_details(transform)
        return DrivingObservation(
            state=state,
            front_camera_rgb=image_rgb,
            lane_offset_m=lane_offset_m,
            heading_error_deg=heading_error_deg,
            lane_details=lane_details,
            collision_detected=collision_details is not None,
            collision_details=collision_details,
            obstacle_details=obstacle_details,
            traffic_rule_details=traffic_rule_details,
        )

    def _adjust_spawn_transform(self, transform: Any) -> Any:
        if self._carla is None:
            return transform

        yaw_deg = transform.rotation.yaw + self.config.spawn_yaw_offset_deg
        yaw_rad = math.radians(transform.rotation.yaw + 90.0)
        lateral_offset = self.config.spawn_lateral_offset_m
        location = self._carla.Location(
            x=transform.location.x + math.cos(yaw_rad) * lateral_offset,
            y=transform.location.y + math.sin(yaw_rad) * lateral_offset,
            z=transform.location.z,
        )
        rotation = self._carla.Rotation(
            pitch=transform.rotation.pitch,
            yaw=yaw_deg,
            roll=transform.rotation.roll,
        )
        return self._carla.Transform(location, rotation)

    def _lane_metrics(
        self,
        transform: Any,
    ) -> tuple[float | None, float | None, dict[str, Any] | None]:
        if self._world is None or self._carla is None:
            return None, None, None

        try:
            waypoint = self._world.get_map().get_waypoint(
                transform.location,
                project_to_road=True,
                lane_type=self._carla.LaneType.Driving,
            )
        except Exception:
            return None, None, None

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
        lane_details = {
            "road_id": int(waypoint.road_id),
            "section_id": int(waypoint.section_id),
            "lane_id": int(waypoint.lane_id),
            "lane_width_m": float(waypoint.lane_width),
            "is_junction": bool(waypoint.is_junction),
        }
        return float(lateral_offset_m), float(heading_error_deg), lane_details

    def _traffic_rule_details(self, transform: Any) -> dict[str, Any] | None:
        traffic_light = self._traffic_light_details(transform)
        stop_sign = self._stop_sign_details(transform)
        if traffic_light is None and stop_sign is None:
            return None
        return {
            "traffic_light": traffic_light,
            "stop_sign": stop_sign,
        }

    def _traffic_light_details(self, transform: Any) -> dict[str, Any] | None:
        if self._vehicle is None:
            return None

        ego_waypoint = None
        with suppress(Exception):
            ego_waypoint = self._world.get_map().get_waypoint(
                transform.location,
                project_to_road=True,
                lane_type=self._carla.LaneType.Driving,
            )

        with suppress(Exception):
            if self._vehicle.is_at_traffic_light():
                traffic_light = self._vehicle.get_traffic_light()
                if traffic_light is not None:
                    details = self._traffic_actor_details(
                        traffic_light,
                        transform,
                        state=str(self._vehicle.get_traffic_light_state()).split(".")[-1],
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
                # CARLA lane ids use opposite signs for opposite travel directions.
                # On the same road, keep trusting lane metadata so a broad trigger
                # volume cannot make us stop for a sign on the opposing lane.
                return int(sign_lane_id) == int(ego_waypoint.lane_id)
            # Stop signs at intersections often project to the cross street even
            # when their trigger box covers the ego lane's stopping zone.
            return True

        if sign_road_id is not None and sign_lane_id is not None:
            return self._stop_sign_lane_matches_ego_lane(details, ego_waypoint)

        # Some maps/actors do not expose lane metadata or a usable trigger
        # volume. Keep those candidates for the stricter geometry fallback below.
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
            return True
        if ego_waypoint is not None and self._stop_sign_lane_matches_ego_lane(
            details,
            ego_waypoint,
        ):
            return abs(details["lateral_distance_m"]) <= 6.0

        # Fallback for maps/actors without usable trigger-volume metadata.
        return abs(details["lateral_distance_m"]) <= 3.4 and abs(details["angle_deg"]) <= 45.0

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
        if self._carla is None:
            return None
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

    def _read_camera_image(self, target_frame: int) -> np.ndarray:
        deadline = time.monotonic() + self.config.timeout_seconds
        image = None
        while time.monotonic() < deadline:
            timeout = max(0.01, deadline - time.monotonic())
            try:
                candidate = self._image_queue.get(timeout=timeout)
            except queue.Empty as exc:
                raise RuntimeError("Timed out waiting for CARLA camera frames.") from exc
            image = candidate
            # Ignore older buffered frames until the camera catches up with the world snapshot.
            if getattr(candidate, "frame", -1) >= target_frame:
                break

        if image is None:
            raise RuntimeError("No CARLA camera frame was received.")

        array = np.frombuffer(image.raw_data, dtype=np.uint8)
        array = array.reshape((image.height, image.width, 4))
        rgb = array[:, :, :3][:, :, ::-1].copy()
        return rgb

    def _on_collision(self, event: Any) -> None:
        impulse = event.normal_impulse
        actor_details = self._actor_details(event.other_actor)
        self._collision_events.put(
            {
                "frame": int(event.frame),
                "other_actor": actor_details,
                "impulse_magnitude": float(
                    math.sqrt(impulse.x**2 + impulse.y**2 + impulse.z**2)
                ),
                "normal_impulse": {
                    "x": float(impulse.x),
                    "y": float(impulse.y),
                    "z": float(impulse.z),
                },
            }
        )

    def _on_obstacle(self, event: Any) -> None:
        self._obstacle_events.put(
            {
                "frame": int(event.frame),
                "distance_m": float(event.distance),
                "other_actor": self._actor_details(event.other_actor),
            }
        )

    def _actor_details(self, actor: Any) -> dict[str, Any] | None:
        if actor is None:
            return None

        attributes = getattr(actor, "attributes", {})
        role_name = attributes.get("role_name") if hasattr(attributes, "get") else None
        return {
            "id": int(actor.id),
            "type_id": str(actor.type_id),
            "role_name": role_name,
        }

    def _consume_collision_details(self, frame: int) -> dict[str, Any] | None:
        while True:
            try:
                self._pending_collision_events.append(self._collision_events.get_nowait())
            except queue.Empty:
                break

        for index, details in enumerate(self._pending_collision_events):
            if int(details["frame"]) <= frame:
                return self._pending_collision_events.pop(index)
        return None

    def _consume_obstacle_details(self, frame: int) -> dict[str, Any] | None:
        while True:
            try:
                self._pending_obstacle_events.append(self._obstacle_events.get_nowait())
            except queue.Empty:
                break

        latest: dict[str, Any] | None = None
        remaining: list[dict[str, Any]] = []
        for details in self._pending_obstacle_events:
            event_frame = int(details["frame"])
            if event_frame <= frame:
                latest = details
            else:
                remaining.append(details)

        self._pending_obstacle_events = remaining
        if latest is None or frame - int(latest["frame"]) > 3:
            return None
        return latest


def normalize_angle_deg(value: float) -> float:
    return ((value + 180.0) % 360.0) - 180.0
