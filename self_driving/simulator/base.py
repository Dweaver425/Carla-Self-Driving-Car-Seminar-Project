from __future__ import annotations

from abc import ABC, abstractmethod

from self_driving.types import ControlCommand, DrivingObservation


class SimulatorClient(ABC):
    @abstractmethod
    def setup(self) -> None:
        """Prepare the simulator backend."""

    @abstractmethod
    def get_observation(self) -> DrivingObservation:
        """Return the current observation before the next control command."""

    @abstractmethod
    def step(self, command: ControlCommand) -> DrivingObservation:
        """Advance one control step and return the latest observation."""

    @abstractmethod
    def teardown(self) -> None:
        """Release resources owned by the backend."""
