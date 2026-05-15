from __future__ import annotations

from argparse import Namespace
from pathlib import Path

from main import read_dataset_file, resolve_training_dataset_dirs


def test_read_dataset_file_ignores_blank_lines_and_comments(tmp_path: Path) -> None:
    dataset_file = tmp_path / "datasets.txt"
    dataset_file.write_text(
        "\n"
        "# collected overnight chunks\n"
        "data/episodes/run/chunk_1/vehicle_01\n"
        "  data/episodes/run/chunk_1/vehicle_02  \n",
        encoding="utf-8",
    )

    assert read_dataset_file(dataset_file) == [
        Path("data/episodes/run/chunk_1/vehicle_01"),
        Path("data/episodes/run/chunk_1/vehicle_02"),
    ]


def test_resolve_training_dataset_dirs_combines_cli_and_file(tmp_path: Path) -> None:
    dataset_file = tmp_path / "datasets.txt"
    dataset_file.write_text("data/episodes/file_dataset\n", encoding="utf-8")
    args = Namespace(
        dataset=["data/episodes/cli_dataset"],
        dataset_file=[str(dataset_file)],
    )

    assert resolve_training_dataset_dirs(args) == [
        Path("data/episodes/cli_dataset"),
        Path("data/episodes/file_dataset"),
    ]
