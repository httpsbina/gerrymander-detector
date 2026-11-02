"""Checkpoint provenance rejection and exact continuation on a synthetic grid."""

import csv
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from src.chain.checkpoint_integrity import protect_run, validate_checkpoint

try:
    import geopandas as gpd
    from shapely.geometry import box
except ModuleNotFoundError:
    gpd = None

ROOT = Path(__file__).resolve().parents[1]


class CheckpointIntegrityTests(unittest.TestCase):
    def test_legacy_and_mismatched_provenance_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "Legacy"):
            validate_checkpoint({"version": 1}, {}, 7)
        checkpoint = {"version": 2, "seed": 7, "next_step": 10,
                      "provenance": {"configuration": {"epsilon": 0.005}}}
        with self.assertRaisesRegex(ValueError, "configuration"):
            validate_checkpoint(checkpoint, {"configuration": {"epsilon": 0.01}}, 7)
        with self.assertRaisesRegex(ValueError, "seed"):
            validate_checkpoint(checkpoint, checkpoint["provenance"], 8)

    def test_overlap_and_checkpoint_collisions_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "fixture_chain_eps0p005_seed7_steps000000-000099.csv").write_text("fixture")
            with self.assertRaisesRegex(FileExistsError, "overlapping"):
                protect_run(root, root, "fixture", 0.005, 7, 50, 100)
            (root / "fixture_checkpoint_eps0p005_seed7_next200.pkl").write_text("fixture")
            with self.assertRaisesRegex(FileExistsError, "checkpoint"):
                protect_run(root, root, "fixture", 0.005, 7, 100, 100)


@unittest.skipIf(gpd is None, "Scientific environment required for continuation test")
class ContinuationIntegrationTests(unittest.TestCase):
    def test_split_run_matches_uninterrupted_run_including_periodic_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shapes, district, dem, rep = [], [], [], []
            for x in range(6):
                for y in range(6):
                    shapes.append(box(x, y, x + 1, y + 1))
                    district.append((x // 3) * 2 + y // 3 + 1)
                    dem.append(10 + x * 3 + y)
                    rep.append(45 - x * 3 - y)
            dataset = root / "synthetic.gpkg"
            gpd.GeoDataFrame({"district": district, "population": [100] * 36,
                              "dem": dem, "rep": rep}, geometry=shapes, crs="EPSG:5070").to_file(dataset, layer="precincts")
            common = [sys.executable, str(ROOT / "src/chain/run_ensemble.py"),
                      "--state", "Fixture", "--dataset", str(dataset), "--assignment-col", "district",
                      "--population-col", "population", "--dem-col", "dem", "--rep-col", "rep",
                      "--epsilon", "0.01", "--seed", "17"]
            env = dict(os.environ, PYTHONHASHSEED="0", PYTHONUNBUFFERED="1")
            def run(folder, steps, checkpoint=None):
                command = common + ["--steps", str(steps), "--output-dir", str(root / folder),
                                    "--checkpoint-dir", str(root / folder / "checkpoints")]
                if checkpoint:
                    command += ["--resume-from", str(checkpoint)]
                result = subprocess.run(command, capture_output=True, text=True, env=env, timeout=120)
                self.assertEqual(result.returncode, 0, result.stdout[-3000:] + result.stderr[-3000:])
            run("whole", 120)
            run("split", 100)
            checkpoint = root / "split/checkpoints/fixture_checkpoint_eps0p01_seed17_next100.pkl"
            run("split", 20, checkpoint)
            def rows(folder):
                result = []
                for path in sorted((root / folder).glob("*.csv")):
                    with path.open() as stream:
                        result.extend(csv.DictReader(stream))
                return result
            self.assertEqual(rows("whole"), rows("split"))
