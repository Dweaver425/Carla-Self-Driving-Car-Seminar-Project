from __future__ import annotations

from self_driving.control import DemoController
from self_driving.pipeline import run_loop
from self_driving.simulator.base import SimulatorClient


def run_demo(client: SimulatorClient, steps: int) -> None:
    run_loop(client=client, controller=DemoController(), steps=steps, print_payload=True)
