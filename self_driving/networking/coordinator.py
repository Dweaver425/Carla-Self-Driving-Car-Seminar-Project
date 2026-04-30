from __future__ import annotations

import json
import math
import sqlite3
import threading
from pathlib import Path
from typing import Any

from self_driving.networking.messages import CollisionAlert, FleetMessage


class FleetCoordinator:
    def __init__(
        self,
        db_path: str | Path,
        proximity_threshold_m: float = 8.0,
        stale_after_seconds: float = 2.0,
    ) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.proximity_threshold_m = proximity_threshold_m
        self.stale_after_seconds = stale_after_seconds
        self._lock = threading.Lock()
        self._connection = sqlite3.connect(self.db_path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._ensure_schema()

    def close(self) -> None:
        self._connection.close()

    def ingest(self, message: FleetMessage) -> list[CollisionAlert]:
        with self._lock:
            self._insert_telemetry(message)
            alerts = self._detect_alerts(message)
            self._insert_alerts(alerts)
            self._connection.commit()
        return alerts

    def latest_vehicle_snapshots(self) -> list[dict[str, Any]]:
        query = """
            SELECT t.vehicle_id, t.timestamp, t.x, t.y, t.yaw_deg, t.speed_mps
            FROM telemetry AS t
            INNER JOIN (
                SELECT vehicle_id, MAX(timestamp) AS latest_timestamp
                FROM telemetry
                GROUP BY vehicle_id
            ) AS latest
                ON latest.vehicle_id = t.vehicle_id
               AND latest.latest_timestamp = t.timestamp
            ORDER BY t.vehicle_id
        """
        with self._lock:
            rows = self._connection.execute(query).fetchall()
        return [dict(row) for row in rows]

    def _ensure_schema(self) -> None:
        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS telemetry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vehicle_id TEXT NOT NULL,
                frame INTEGER NOT NULL,
                timestamp REAL NOT NULL,
                x REAL NOT NULL,
                y REAL NOT NULL,
                yaw_deg REAL NOT NULL,
                speed_mps REAL NOT NULL,
                confidence REAL NOT NULL,
                predicted_path_json TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_telemetry_vehicle_time
            ON telemetry(vehicle_id, timestamp DESC);

            CREATE TABLE IF NOT EXISTS collision_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject_vehicle_id TEXT NOT NULL,
                other_vehicle_id TEXT NOT NULL,
                timestamp REAL NOT NULL,
                distance_m REAL NOT NULL,
                reason TEXT NOT NULL
            );
            """
        )
        self._connection.commit()

    def _insert_telemetry(self, message: FleetMessage) -> None:
        self._connection.execute(
            """
            INSERT INTO telemetry (
                vehicle_id, frame, timestamp, x, y, yaw_deg, speed_mps, confidence, predicted_path_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                message.vehicle_id,
                message.frame,
                message.timestamp,
                message.x,
                message.y,
                message.yaw_deg,
                message.speed_mps,
                message.confidence,
                json.dumps(message.predicted_path),
            ),
        )

    def _detect_alerts(self, message: FleetMessage) -> list[CollisionAlert]:
        rows = self._connection.execute(
            """
            SELECT vehicle_id, timestamp, x, y, speed_mps, predicted_path_json
            FROM telemetry
            WHERE vehicle_id != ? AND timestamp >= ?
            ORDER BY timestamp DESC
            """,
            (message.vehicle_id, message.timestamp - self.stale_after_seconds),
        ).fetchall()

        latest_by_vehicle: dict[str, sqlite3.Row] = {}
        for row in rows:
            latest_by_vehicle.setdefault(str(row["vehicle_id"]), row)

        alerts: list[CollisionAlert] = []
        for row in latest_by_vehicle.values():
            distance = math.hypot(message.x - row["x"], message.y - row["y"])
            other_path = json.loads(row["predicted_path_json"])
            path_distance = self._minimum_path_distance(message.predicted_path, other_path)

            threshold = self.proximity_threshold_m
            if path_distance <= threshold * 0.6:
                alerts.append(
                    CollisionAlert(
                        subject_vehicle_id=message.vehicle_id,
                        other_vehicle_id=str(row["vehicle_id"]),
                        timestamp=message.timestamp,
                        distance_m=path_distance,
                        reason="predicted_path_overlap",
                    )
                )
                continue

            if distance <= threshold:
                alerts.append(
                    CollisionAlert(
                        subject_vehicle_id=message.vehicle_id,
                        other_vehicle_id=str(row["vehicle_id"]),
                        timestamp=message.timestamp,
                        distance_m=distance,
                        reason="proximity",
                    )
                )

        return alerts

    def _minimum_path_distance(
        self,
        path_a: list[tuple[float, float]],
        path_b: list[list[float]] | list[tuple[float, float]],
    ) -> float:
        if not path_a or not path_b:
            return float("inf")

        best = float("inf")
        for ax, ay in path_a:
            for bx, by in path_b:
                best = min(best, math.hypot(ax - bx, ay - by))
        return best

    def _insert_alerts(self, alerts: list[CollisionAlert]) -> None:
        for alert in alerts:
            self._connection.execute(
                """
                INSERT INTO collision_alerts (
                    subject_vehicle_id, other_vehicle_id, timestamp, distance_m, reason
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    alert.subject_vehicle_id,
                    alert.other_vehicle_id,
                    alert.timestamp,
                    alert.distance_m,
                    alert.reason,
                ),
            )
