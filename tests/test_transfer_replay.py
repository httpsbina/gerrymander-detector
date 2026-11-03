"""Transferred checkpoints must reject incompatible runtimes before sampling."""

from pathlib import Path
import pickle
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from src.chain.benchmark_baselines import checkpoint_path
from src.chain.resume_transfer import replay


class TransferReplayTests(unittest.TestCase):
    def test_runtime_mismatch_refuses_before_creating_outputs(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = root / "chains/ensembles"
            directory.mkdir(parents=True)
            (root / "chains/checkpoints").mkdir()
            experiment = {"input_dir": "chains/ensembles", "prefix": "fixture",
                          "epsilon": 0.001, "steps": 200}
            checkpoint = {"provenance": {"runtime": {"python": "incompatible", "platform": "fixture", "packages": {}}}}
            with checkpoint_path(directory.parent / "checkpoints", experiment, 7, 200).open("wb") as stream:
                pickle.dump(checkpoint, stream)
            destination = root / "replay"
            with patch("src.chain.resume_transfer.ROOT", root), patch("src.chain.resume_transfer.subprocess.run") as run:
                with self.assertRaisesRegex(ValueError, "Runtime differs"):
                    replay("fixture", experiment, 7, destination)
                run.assert_not_called()
            self.assertFalse(destination.exists())


if __name__ == "__main__":
    unittest.main()
