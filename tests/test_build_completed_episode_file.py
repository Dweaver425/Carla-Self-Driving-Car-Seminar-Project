from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_completed_episode_file import build_episode_file


def write_episode(
    path: Path,
    *,
    status: str = "completed",
    frames: int = 3,
    manifest_text: str = "{}\n",
) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "manifest.jsonl").write_text(manifest_text, encoding="utf-8")
    (path / "metadata.json").write_text(
        json.dumps({"frames_recorded": frames, "status": status}),
        encoding="utf-8",
    )


class BuildCompletedEpisodeFileTests(unittest.TestCase):
    def test_builds_relative_list_and_skips_empty_or_incomplete_runs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "episodes"
            write_episode(root / "good_run")
            write_episode(root / "nested" / "chunk_1" / "vehicle_01", frames=5)
            write_episode(root / "bad_empty", manifest_text="")
            write_episode(root / "bad_status", status="started")
            write_episode(root / "bad_zero", frames=0)
            output = Path(tmp) / "tar_shards" / "episodes.txt"
            summary_output = Path(tmp) / "tar_shards" / "summary.json"

            summary = build_episode_file(
                episode_root=root,
                output=output,
                summary_output=summary_output,
            )

            self.assertEqual(
                output.read_text(encoding="utf-8").splitlines(),
                ["good_run", "nested/chunk_1/vehicle_01"],
            )
            self.assertEqual(summary["episodes"], 2)
            self.assertEqual(summary["frames_from_metadata"], 8)
            self.assertEqual(summary["skipped"]["empty_manifest"], 1)
            self.assertEqual(summary["skipped"]["not_completed"], 1)
            self.assertEqual(summary["skipped"]["zero_frames"], 1)
            self.assertTrue(summary_output.exists())


if __name__ == "__main__":
    unittest.main()
