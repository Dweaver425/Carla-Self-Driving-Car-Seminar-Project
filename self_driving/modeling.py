from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch import nn

TARGET_ORDER = ("throttle", "steering", "brake")


def select_torch_device(requested: str | None = None) -> torch.device:
    # Respect an explicit override first, then pick the fastest available backend.
    if requested:
        return torch.device(requested)
    if torch.backends.mps.is_available():
        return torch.device("mps")
    if torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


def image_to_tensor(image_rgb: np.ndarray) -> torch.Tensor:
    tensor = torch.from_numpy(image_rgb).permute(2, 0, 1).float().div(255.0)
    return tensor


class DrivingModel(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        # A small CNN keeps training and inference lightweight for seminar-scale experiments.
        self.network = nn.Sequential(
            nn.Conv2d(3, 16, kernel_size=5, stride=2, padding=2),
            nn.ReLU(),
            nn.Conv2d(16, 32, kernel_size=5, stride=2, padding=2),
            nn.ReLU(),
            nn.Conv2d(32, 64, kernel_size=3, stride=2, padding=1),
            nn.ReLU(),
            nn.Conv2d(64, 128, kernel_size=3, stride=2, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool2d((1, 1)),
            nn.Flatten(),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Linear(64, len(TARGET_ORDER)),
        )

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        return self.network(inputs)


def load_driving_model(
    checkpoint_path: str | Path,
    device: str | None = None,
) -> tuple[DrivingModel, torch.device, dict[str, Any]]:
    checkpoint_path = Path(checkpoint_path)
    if not checkpoint_path.exists():
        raise FileNotFoundError(f"Checkpoint not found: {checkpoint_path}")

    # Load everything onto the active device so inference can run without extra transfers.
    resolved_device = select_torch_device(device)
    checkpoint = torch.load(checkpoint_path, map_location=resolved_device)
    model = DrivingModel()
    model.load_state_dict(checkpoint["model_state"])
    model.to(resolved_device)
    model.eval()
    return model, resolved_device, checkpoint
