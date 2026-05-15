from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class SpawnCandidate:
    spawn_index: int
    stop_sign_id: int
    distance_along_path_m: float
    closest_distance_m: float
    road_id: int | None
    lane_id: int | None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Find CARLA spawn indices whose forward route passes near stop signs."
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--count", type=int, default=2)
    parser.add_argument("--lookahead-m", type=float, default=140.0)
    parser.add_argument("--step-m", type=float, default=2.0)
    parser.add_argument("--near-m", type=float, default=12.0)
    parser.add_argument("--format", choices=("plain", "json"), default="json")
    return parser.parse_args()


def distance_2d(a: Any, b: Any) -> float:
    return math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2)


def stop_sign_location(stop_sign: Any) -> Any:
    transform = stop_sign.get_transform()
    trigger_volume = getattr(stop_sign, "trigger_volume", None)
    if trigger_volume is None:
        return transform.location
    return transform.transform(trigger_volume.location)


def waypoint_lane_ids(waypoint: Any | None) -> tuple[int | None, int | None]:
    if waypoint is None:
        return None, None
    return int(waypoint.road_id), int(waypoint.lane_id)


def sample_waypoints(start_waypoint: Any, lookahead_m: float, step_m: float) -> list[tuple[float, Any]]:
    samples: list[tuple[float, Any]] = []
    distance_m = 0.0
    waypoint = start_waypoint
    while distance_m <= lookahead_m:
        samples.append((distance_m, waypoint))
        next_waypoints = waypoint.next(step_m)
        if not next_waypoints:
            break
        waypoint = next_waypoints[0]
        distance_m += step_m
    return samples


def find_candidates(args: argparse.Namespace) -> list[SpawnCandidate]:
    import carla

    client = carla.Client(args.host, args.port)
    client.set_timeout(args.timeout)
    world = client.get_world()
    carla_map = world.get_map()
    spawn_points = carla_map.get_spawn_points()
    stop_signs = list(world.get_actors().filter("*stop*"))
    if not spawn_points:
        raise RuntimeError("No spawn points are available in the current CARLA map.")
    if not stop_signs:
        raise RuntimeError("No stop sign actors were found in the current CARLA world.")

    stop_locations = [
        (int(stop_sign.id), stop_sign_location(stop_sign), carla_map.get_waypoint(
            stop_sign_location(stop_sign),
            project_to_road=True,
            lane_type=carla.LaneType.Driving,
        ))
        for stop_sign in stop_signs
    ]

    candidates: list[SpawnCandidate] = []
    for spawn_index, spawn_transform in enumerate(spawn_points):
        start_waypoint = carla_map.get_waypoint(
            spawn_transform.location,
            project_to_road=True,
            lane_type=carla.LaneType.Driving,
        )
        if start_waypoint is None:
            continue

        best_for_spawn: SpawnCandidate | None = None
        for distance_along, waypoint in sample_waypoints(
            start_waypoint,
            args.lookahead_m,
            args.step_m,
        ):
            waypoint_location = waypoint.transform.location
            for stop_id, stop_location, stop_waypoint in stop_locations:
                stop_road_id, stop_lane_id = waypoint_lane_ids(stop_waypoint)
                if stop_road_id is not None and int(waypoint.road_id) != stop_road_id:
                    continue
                if stop_lane_id is not None and int(waypoint.lane_id) != stop_lane_id:
                    continue
                closest = distance_2d(waypoint_location, stop_location)
                if closest > args.near_m:
                    continue
                candidate = SpawnCandidate(
                    spawn_index=spawn_index,
                    stop_sign_id=stop_id,
                    distance_along_path_m=round(distance_along, 3),
                    closest_distance_m=round(closest, 3),
                    road_id=int(waypoint.road_id),
                    lane_id=int(waypoint.lane_id),
                )
                if (
                    best_for_spawn is None
                    or candidate.distance_along_path_m < best_for_spawn.distance_along_path_m
                ):
                    best_for_spawn = candidate

        if best_for_spawn is not None:
            candidates.append(best_for_spawn)

    return sorted(
        candidates,
        key=lambda item: (item.distance_along_path_m, item.closest_distance_m, item.spawn_index),
    )


def select_distinct_candidates(candidates: list[SpawnCandidate], count: int) -> list[SpawnCandidate]:
    selected: list[SpawnCandidate] = []
    used_spawns: set[int] = set()
    used_stops: set[int] = set()

    for candidate in candidates:
        if candidate.spawn_index in used_spawns:
            continue
        if candidate.stop_sign_id in used_stops:
            continue
        selected.append(candidate)
        used_spawns.add(candidate.spawn_index)
        used_stops.add(candidate.stop_sign_id)
        if len(selected) >= count:
            return selected

    for candidate in candidates:
        if candidate.spawn_index in used_spawns:
            continue
        selected.append(candidate)
        used_spawns.add(candidate.spawn_index)
        if len(selected) >= count:
            break
    return selected


def main() -> None:
    args = parse_args()
    candidates = find_candidates(args)
    selected = select_distinct_candidates(candidates, args.count)
    if args.format == "plain":
        print(" ".join(str(candidate.spawn_index) for candidate in selected))
        return
    print(
        json.dumps(
            {
                "selected_spawn_indices": [candidate.spawn_index for candidate in selected],
                "selected": [asdict(candidate) for candidate in selected],
                "candidate_count": len(candidates),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
