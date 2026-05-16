from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.analyze_intersection_frames import main, summarize_root


def write_metadata(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "metadata.json").write_text(
        json.dumps({"status": "completed", "controller": "model_autopilot_guide"}),
        encoding="utf-8",
    )


class AnalyzeIntersectionFramesTests(unittest.TestCase):
    def test_completed_empty_manifest_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            episode = Path(tmp) / "teacher"
            write_metadata(episode)
            (episode / "manifest.jsonl").write_text("", encoding="utf-8")

            with self.assertRaisesRegex(SystemExit, "No completed non-empty"):
                summarize_root(episode, top_k=3)

    def test_teacher_dataset_file_is_not_written_without_junction_frames(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            episode = Path(tmp) / "teacher"
            dataset_file = Path(tmp) / "teacher_datasets.txt"
            write_metadata(episode)
            (episode / "manifest.jsonl").write_text(
                json.dumps(
                    {
                        "frame": 1,
                        "lane_details": {"is_junction": False},
                        "lane_offset_m": 0.0,
                        "heading_error_deg": 0.0,
                        "control": {"throttle": 0.1, "steering": 0.0, "brake": 0.0},
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            argv = [
                "analyze_intersection_frames.py",
                "--teacher-root",
                str(episode),
                "--write-teacher-dataset",
                str(dataset_file),
            ]
            with patch.object(sys, "argv", argv):
                with self.assertRaisesRegex(SystemExit, "not writing an empty"):
                    main()

            self.assertFalse(dataset_file.exists())


if __name__ == "__main__":
    unittest.main()
