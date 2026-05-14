from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import time
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
    log_interval: int = 100


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
    device = select_torch_device(config.device)
    if device.type == "cuda":
        torch.backends.cudnn.benchmark = True
        torch.set_float32_matmul_precision("high")

    pin_memory = device.type == "cuda"
    loader_kwargs: dict[str, Any] = {
        "batch_size": config.batch_size,
        "num_workers": config.num_workers,
        "pin_memory": pin_memory,
    }
    if config.num_workers > 0:
        # Keep worker processes alive between epochs so image loading stays warm.
        loader_kwargs["persistent_workers"] = True
        loader_kwargs["prefetch_factor"] = 2

    train_loader = DataLoader(train_dataset, shuffle=True, **loader_kwargs)
    val_loader = (
        DataLoader(val_dataset, shuffle=False, **loader_kwargs)
        if len(val_dataset) > 0
        else None
    )

    model = DrivingModel().to(device)
    if device.type == "cuda":
        model = model.to(memory_format=torch.channels_last)
    optimizer = torch.optim.Adam(model.parameters(), lr=config.learning_rate)
    loss_fn = nn.MSELoss()
    amp_enabled = device.type == "cuda"
    scaler = torch.amp.GradScaler("cuda", enabled=amp_enabled)

    final_train_loss = 0.0
    final_val_loss = 0.0
    config.output_path.parent.mkdir(parents=True, exist_ok=True)
    print(
        {
            "event": "training_start",
            "batch_size": config.batch_size,
            "device": str(device),
            "epochs": config.epochs,
            "num_workers": config.num_workers,
            "samples": total_samples,
            "train_samples": len(train_dataset),
            "val_samples": len(val_dataset),
            "amp": amp_enabled,
        },
        flush=True,
    )
    for epoch in range(1, config.epochs + 1):
        final_train_loss = train_one_epoch(
            model,
            train_loader,
            optimizer,
            loss_fn,
            device,
            scaler=scaler,
            amp_enabled=amp_enabled,
            epoch=epoch,
            total_epochs=config.epochs,
            log_interval=config.log_interval,
        )
        if val_loader is not None:
            final_val_loss = evaluate(
                model,
                val_loader,
                loss_fn,
                device,
                amp_enabled=amp_enabled,
                epoch=epoch,
                total_epochs=config.epochs,
            )
        print(
            {
                "event": "epoch_complete",
                "epoch": epoch,
                "epochs": config.epochs,
                "train_loss": final_train_loss,
                "val_loss": final_val_loss,
            },
            flush=True,
        )
        checkpoint = build_checkpoint(
            model=model,
            config=config,
            total_samples=total_samples,
            image_shape=image_shape,
            device=device,
            amp_enabled=amp_enabled,
            train_loss=final_train_loss,
            val_loss=final_val_loss,
            epoch=epoch,
        )
        epoch_path = config.output_path.with_name(
            f"{config.output_path.stem}_epoch_{epoch:02d}{config.output_path.suffix}"
        )
        torch.save(checkpoint, epoch_path)
        torch.save(checkpoint, config.output_path)
        print(
            {
                "event": "checkpoint_saved",
                "epoch": epoch,
                "checkpoint": str(config.output_path),
                "epoch_checkpoint": str(epoch_path),
            },
            flush=True,
        )

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


def build_checkpoint(
    *,
    model: nn.Module,
    config: TrainingConfig,
    total_samples: int,
    image_shape: tuple[int, ...] | None,
    device: torch.device,
    amp_enabled: bool,
    train_loss: float,
    val_loss: float,
    epoch: int,
) -> dict[str, Any]:
    # Save enough metadata with the checkpoint to explain how the model was trained later.
    return {
        "model_state": model.state_dict(),
        "target_order": TARGET_ORDER,
        "training": {
            "epochs": config.epochs,
            "completed_epoch": epoch,
            "batch_size": config.batch_size,
            "learning_rate": config.learning_rate,
            "log_interval": config.log_interval,
            "train_loss": train_loss,
            "val_loss": val_loss,
            "device": str(device),
            "amp": amp_enabled,
        },
        "dataset": {
            "paths": [str(path) for path in config.dataset_dirs],
            "samples": total_samples,
            "image_shape": image_shape,
        },
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
    *,
    scaler: torch.amp.GradScaler,
    amp_enabled: bool,
    epoch: int,
    total_epochs: int,
    log_interval: int,
) -> float:
    model.train()
    total_loss = 0.0
    total_samples = 0
    started_at = time.perf_counter()
    total_batches = len(loader)
    non_blocking = device.type == "cuda"
    for batch_index, (images, targets) in enumerate(loader, start=1):
        images = images.to(device, non_blocking=non_blocking)
        targets = targets.to(device, non_blocking=non_blocking)
        if device.type == "cuda":
            images = images.contiguous(memory_format=torch.channels_last)

        optimizer.zero_grad(set_to_none=True)
        with torch.amp.autocast(device_type=device.type, enabled=amp_enabled):
            predictions = model(images)
            loss = loss_fn(predictions, targets)
        scaler.scale(loss).backward()
        scaler.step(optimizer)
        scaler.update()

        batch_size = images.shape[0]
        total_loss += float(loss.item()) * batch_size
        total_samples += batch_size
        if log_interval > 0 and batch_index % log_interval == 0:
            elapsed = max(0.001, time.perf_counter() - started_at)
            print(
                {
                    "event": "train_progress",
                    "epoch": epoch,
                    "epochs": total_epochs,
                    "batch": batch_index,
                    "batches": total_batches,
                    "samples": total_samples,
                    "samples_per_second": round(total_samples / elapsed, 2),
                    "loss": total_loss / max(total_samples, 1),
                },
                flush=True,
            )
    return total_loss / max(total_samples, 1)


def evaluate(
    model: DrivingModel,
    loader: DataLoader[tuple[torch.Tensor, torch.Tensor]],
    loss_fn: nn.Module,
    device: torch.device,
    *,
    amp_enabled: bool,
    epoch: int,
    total_epochs: int,
) -> float:
    model.eval()
    total_loss = 0.0
    total_samples = 0
    started_at = time.perf_counter()
    non_blocking = device.type == "cuda"
    with torch.no_grad():
        for images, targets in loader:
            images = images.to(device, non_blocking=non_blocking)
            targets = targets.to(device, non_blocking=non_blocking)
            if device.type == "cuda":
                images = images.contiguous(memory_format=torch.channels_last)
            with torch.amp.autocast(device_type=device.type, enabled=amp_enabled):
                predictions = model(images)
                loss = loss_fn(predictions, targets)
            batch_size = images.shape[0]
            total_loss += float(loss.item()) * batch_size
            total_samples += batch_size
    elapsed = max(0.001, time.perf_counter() - started_at)
    print(
        {
            "event": "val_complete",
            "epoch": epoch,
            "epochs": total_epochs,
            "samples": total_samples,
            "samples_per_second": round(total_samples / elapsed, 2),
            "loss": total_loss / max(total_samples, 1),
        },
        flush=True,
    )
    return total_loss / max(total_samples, 1)
