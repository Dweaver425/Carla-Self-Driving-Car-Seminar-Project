from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import torch
from torch import nn
from torch.utils.data import ConcatDataset, DataLoader, Dataset, random_split

from self_driving.data.dataset import DrivingDataset
from self_driving.modeling import DrivingModel, TARGET_ORDER, select_torch_device


@dataclass(slots=True)
class TrainingConfig:
    dataset_dirs: list[Path]
    output_path: Path
    epochs: int = 5
    batch_size: int = 16
    learning_rate: float = 1e-3
    val_split: float = 0.2
    device: str | None = None
    num_workers: int = 0


def train_model(config: TrainingConfig) -> dict[str, Any]:
    datasets = [DrivingDataset(path) for path in config.dataset_dirs]
    if not datasets:
        raise ValueError("At least one dataset directory is required for training.")

    dataset: Dataset[tuple[torch.Tensor, torch.Tensor]]
    if len(datasets) == 1:
        dataset = datasets[0]
    else:
        dataset = ConcatDataset(datasets)

    total_samples = sum(len(item) for item in datasets)
    image_shape = datasets[0].image_shape
    train_dataset, val_dataset = split_dataset(dataset, config.val_split)
    loader_kwargs: dict[str, Any] = {
        "batch_size": config.batch_size,
        "num_workers": config.num_workers,
    }
    if config.num_workers > 0:
        # Keep worker processes alive between epochs so image loading stays warm.
        loader_kwargs["persistent_workers"] = True

    train_loader = DataLoader(train_dataset, shuffle=True, **loader_kwargs)
    val_loader = (
        DataLoader(val_dataset, shuffle=False, **loader_kwargs)
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
    # Save enough metadata with the checkpoint to explain how the model was trained later.
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
            "paths": [str(path) for path in config.dataset_dirs],
            "samples": total_samples,
            "image_shape": image_shape,
        },
    }
    torch.save(checkpoint, config.output_path)

    return {
        "batch_size": config.batch_size,
        "checkpoint": str(config.output_path),
        "datasets": [str(path) for path in config.dataset_dirs],
        "device": str(device),
        "epochs": config.epochs,
        "num_workers": config.num_workers,
        "samples": total_samples,
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
    # Use a fixed seed so repeated training runs split the same way by default.
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
