from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from self_driving.networking.coordinator import FleetCoordinator
from self_driving.networking.messages import FleetMessage


class CoordinatorHTTPServer(ThreadingHTTPServer):
    def __init__(self, server_address: tuple[str, int], coordinator: FleetCoordinator) -> None:
        super().__init__(server_address, TelemetryRequestHandler)
        self.coordinator = coordinator


class TelemetryRequestHandler(BaseHTTPRequestHandler):
    server: CoordinatorHTTPServer

    def do_GET(self) -> None:
        if self.path == "/health":
            self._write_json(200, {"status": "ok"})
            return
        if self.path == "/vehicles":
            snapshots = self.server.coordinator.latest_vehicle_snapshots()
            self._write_json(200, {"vehicles": snapshots})
            return
        self._write_json(404, {"error": "Not found"})

    def do_POST(self) -> None:
        if self.path != "/telemetry":
            self._write_json(404, {"error": "Not found"})
            return

        # Keep the HTTP layer thin: validate the payload, then hand off to the coordinator.
        body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        try:
            payload = json.loads(body.decode("utf-8"))
            message = FleetMessage.from_dict(payload)
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            self._write_json(400, {"error": "Invalid telemetry payload"})
            return

        alerts = self.server.coordinator.ingest(message)
        self._write_json(
            200,
            {"status": "ok", "alerts": [alert.as_dict() for alert in alerts]},
        )

    def log_message(self, format: str, *args: Any) -> None:
        return None

    def _write_json(self, status_code: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, sort_keys=True).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def serve_coordinator(
    host: str,
    port: int,
    db_path: str | Path,
    proximity_threshold_m: float = 8.0,
    stale_after_seconds: float = 2.0,
) -> None:
    coordinator = FleetCoordinator(
        db_path=db_path,
        proximity_threshold_m=proximity_threshold_m,
        stale_after_seconds=stale_after_seconds,
    )
    server = CoordinatorHTTPServer((host, port), coordinator)
    print(f"Coordinator listening on http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        coordinator.close()
