from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import torch
from torch import nn
from torch.utils.data import DataLoader, Dataset, random_split

from self_driving.data.dataset import DrivingDataset
from self_driving.modeling import DrivingModel, TARGET_ORDER, select_torch_device


@dataclass(slots=True)
class TrainingConfig:
    dataset_dir: Path
    output_path: Path
    epochs: int = 5
    batch_size: int = 16
    learning_rate: float = 1e-3
    val_split: float = 0.2
    device: str | None = None


def train_model(config: TrainingConfig) -> dict[str, Any]:
    dataset = DrivingDataset(config.dataset_dir)
    train_dataset, val_dataset = split_dataset(dataset, config.val_split)
    train_loader = DataLoader(train_dataset, batch_size=config.batch_size, shuffle=True)
    val_loader = (
        DataLoader(val_dataset, batch_size=config.batch_size, shuffle=False)
        if len(val_dataset) > 0
        else None
    )

    device = select_torch_device(config.device)
    model = DrivingModel().to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=config.learning_rate)
    loss_fn = nn.MSELoss()

    final_train_loss = 0.0
    final_val_loss = 0.0
    for _ in range(config.epochs):
        final_train_loss = train_one_epoch(model, train_loader, optimizer, loss_fn, device)
        if val_loader is not None:
            final_val_loss = evaluate(model, val_loader, loss_fn, device)

    config.output_path.parent.mkdir(parents=True, exist_ok=True)
    checkpoint = {
        "model_state": model.state_dict(),
        "target_order": TARGET_ORDER,
        "training": {
            "epochs": config.epochs,
            "batch_size": config.batch_size,
            "learning_rate": config.learning_rate,
            "train_loss": final_train_loss,
            "val_loss": final_val_loss,
            "device": str(device),
        },
        "dataset": {
            "path": str(config.dataset_dir),
            "samples": len(dataset),
            "image_shape": dataset.image_shape,
        },
    }
    torch.save(checkpoint, config.output_path)

    return {
        "batch_size": config.batch_size,
        "checkpoint": str(config.output_path),
        "dataset": str(config.dataset_dir),
        "device": str(device),
        "epochs": config.epochs,
        "samples": len(dataset),
        "train_loss": final_train_loss,
        "val_loss": final_val_loss,
    }


def split_dataset(dataset: Dataset[Any], val_split: float) -> tuple[Dataset[Any], Dataset[Any]]:
    if len(dataset) < 2 or val_split <= 0.0:
        empty_subset = random_split(dataset, [len(dataset), 0], generator=torch.Generator().manual_seed(42))[1]
        return dataset, empty_subset

    val_size = max(1, int(len(dataset) * val_split))
    val_size = min(val_size, len(dataset) - 1)
    train_size = len(dataset) - val_size
    return random_split(
        dataset,
        [train_size, val_size],
        generator=torch.Generator().manual_seed(42),
    )


def train_one_epoch(
    model: DrivingModel,
    loader: DataLoader[tuple[torch.Tensor, torch.Tensor]],
    optimizer: torch.optim.Optimizer,
    loss_fn: nn.Module,
    device: torch.device,
) -> float:
    model.train()
    total_loss = 0.0
    total_samples = 0
    for images, targets in loader:
        images = images.to(device)
        targets = targets.to(device)

        optimizer.zero_grad()
        predictions = model(images)
        loss = loss_fn(predictions, targets)
        loss.backward()
        optimizer.step()

        batch_size = images.shape[0]
        total_loss += float(loss.item()) * batch_size
        total_samples += batch_size
    return total_loss / max(total_samples, 1)


def evaluate(
    model: DrivingModel,
    loader: DataLoader[tuple[torch.Tensor, torch.Tensor]],
    loss_fn: nn.Module,
    device: torch.device,
) -> float:
    model.eval()
    total_loss = 0.0
    total_samples = 0
    with torch.no_grad():
        for images, targets in loader:
            images = images.to(device)
            targets = targets.to(device)
            predictions = model(images)
            loss = loss_fn(predictions, targets)
            batch_size = images.shape[0]
            total_loss += float(loss.item()) * batch_size
            total_samples += batch_size
    return total_loss / max(total_samples, 1)
