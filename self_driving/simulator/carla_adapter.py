from __future__ import annotations

import math
import queue
import time
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
        self._world: Any = None
        self._vehicle: Any = None
        self._camera: Any = None
        self._collision_sensor: Any = None
        self._image_queue: queue.Queue[Any] = queue.Queue()
        self._latest_collision_frame: int | None = None
        self._original_settings: Any = None
        self._last_command = ControlCommand()

    def setup(self) -> None:
        try:
            import carla
        except ImportError as exc:
            raise RuntimeError(
                "CARLA Python API is not installed. Use '--backend mock' on macOS and "
                "install CARLA on the simulation machine before using '--backend carla'."
            ) from exc

        self._carla = carla
        self._client = carla.Client(self.config.host, self.config.port)
        self._client.set_timeout(self.config.timeout_seconds)
        self._world = self._client.get_world()
        self._original_settings = self._world.get_settings()

        if self.config.synchronous_mode:
            settings = self._world.get_settings()
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

        transform = spawn_points[self.config.spawn_index % len(spawn_points)]
        self._vehicle = self._world.try_spawn_actor(blueprint, transform)
        if self._vehicle is None:
            raise RuntimeError(
                "Failed to spawn the ego vehicle. Try another spawn index or clear the world."
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

        self._tick_world()

    def get_observation(self) -> DrivingObservation:
        return self._capture_observation(self._last_command)

    def step(self, command: ControlCommand) -> DrivingObservation:
        if self._vehicle is None or self._world is None or self._carla is None:
            raise RuntimeError("CARLA backend is not initialized.")

        self._vehicle.apply_control(
            self._carla.VehicleControl(
                throttle=float(command.throttle),
                steer=float(command.steering),
                brake=float(command.brake),
            )
        )
        self._last_command = command
        self._tick_world()
        return self._capture_observation(command)

    def teardown(self) -> None:
        for actor_name in ("_camera", "_collision_sensor", "_vehicle"):
            actor = getattr(self, actor_name)
            if actor is not None:
                actor.destroy()
                setattr(self, actor_name, None)

        if self._world is not None and self._original_settings is not None:
            self._world.apply_settings(self._original_settings)
            self._original_settings = None

    def _tick_world(self) -> None:
        if self._world is None:
            raise RuntimeError("CARLA world is not available.")
        if self.config.synchronous_mode:
            self._world.tick()
        else:
            self._world.wait_for_tick()

    def _capture_observation(self, command: ControlCommand) -> DrivingObservation:
        if self._vehicle is None or self._world is None:
            raise RuntimeError("CARLA backend is not initialized.")

        snapshot = self._world.get_snapshot()
        transform = self._vehicle.get_transform()
        velocity = self._vehicle.get_velocity()
        speed_mps = math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2)
        image_rgb = self._read_camera_image(snapshot.frame)

        state = VehicleState(
            vehicle_id=self.config.ego_vehicle_id,
            timestamp=snapshot.timestamp.elapsed_seconds,
            pose=Pose2D(
                x=transform.location.x,
                y=transform.location.y,
                yaw_deg=transform.rotation.yaw,
            ),
            speed_mps=speed_mps,
            control=command,
            frame=snapshot.frame,
        )
        return DrivingObservation(
            state=state,
            front_camera_rgb=image_rgb,
            collision_detected=self._consume_collision_flag(snapshot.frame),
        )

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
            if getattr(candidate, "frame", -1) >= target_frame:
                break

        if image is None:
            raise RuntimeError("No CARLA camera frame was received.")

        array = np.frombuffer(image.raw_data, dtype=np.uint8)
        array = array.reshape((image.height, image.width, 4))
        rgb = array[:, :, :3][:, :, ::-1].copy()
        return rgb

    def _on_collision(self, event: Any) -> None:
        self._latest_collision_frame = int(event.frame)

    def _consume_collision_flag(self, frame: int) -> bool:
        detected = self._latest_collision_frame is not None and self._latest_collision_frame <= frame
        if detected:
            self._latest_collision_frame = None
        return detected
