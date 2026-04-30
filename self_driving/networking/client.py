from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from self_driving.networking.messages import FleetMessage


class TelemetryPublisher:
    def __init__(self, endpoint: str, timeout_seconds: float = 2.0) -> None:
        self.endpoint = endpoint
        self.timeout_seconds = timeout_seconds

    def publish(self, message: FleetMessage) -> list[dict[str, Any]]:
        payload = json.dumps(message.as_dict()).encode("utf-8")
        request = Request(
            self.endpoint,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError):
            return []

        alerts = body.get("alerts", [])
        return alerts if isinstance(alerts, list) else []
