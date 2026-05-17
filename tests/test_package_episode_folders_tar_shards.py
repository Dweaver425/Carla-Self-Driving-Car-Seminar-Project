from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from package_episode_folders_tar_shards import safe_source_name  # noqa: E402


class PackageEpisodeFoldersTarShardsTests(unittest.TestCase):
    def test_safe_source_name_uses_relative_path_for_nested_episodes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            episode_root = Path(tmp) / "episodes"
            episode = episode_root / "overnight2cars_v3" / "chunk_1" / "vehicle_01"

            self.assertEqual(
                safe_source_name(episode, episode_root=episode_root),
                "overnight2cars_v3_chunk_1_vehicle_01",
            )


if __name__ == "__main__":
    unittest.main()
