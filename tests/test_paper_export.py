"""Paper export preserves frozen values and accepts later registered states."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from paper.export import FIELDS, export, merge_results, publish, sha


class PaperExportTests(unittest.TestCase):
    def test_existing_artifact_is_not_overwritten(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "figure.png"
            publish(path, b"original")
            publish(path, b"original")
            with self.assertRaises(FileExistsError):
                publish(path, b"different")
            self.assertEqual(path.read_bytes(), b"original")

    def test_new_state_keeps_existing_numbers(self):
        previous = {"nc": {"value": 17}, "_paper": {"nc": {"freeze": "fixed"}}}
        current = {**previous, "texas": {"value": 29}, "_paper": {**previous["_paper"], "texas": {"freeze": "new"}}}
        self.assertEqual(merge_results(previous, current)["texas"]["value"], 29)
        current["nc"] = {"value": 18}
        with self.assertRaises(ValueError):
            merge_results(previous, current)

    def make_fixture(self, root):
        state = "texas"
        raw = {"chain_summary": [{"states": 17, "warmup": 2, "retained_states": 15}],
               "primary_diagnostics": {"joint": {"dem_seats": {field: index + 0.25 for index, field in enumerate(FIELDS)}}}}
        (root / "frozen").mkdir()
        (root / "build/texas/figures").mkdir(parents=True)
        (root / "build/texas/audit").mkdir()
        (root / "inputs").mkdir()
        (root / "inputs/fixture_chain_eps0p001_seed71_steps000000-000016.csv").write_text("step,dem_seats\n0,4\n")
        manifest = {"experiments": {"fixture": {"input_dir": "inputs", "prefix": "fixture", "epsilon": 0.001,
                    "seeds": [71], "steps": 17, "warmup": 2, "starting_plan": "fixture-start"}}}
        (root / "frozen/manifest.json").write_text(json.dumps(manifest))
        (root / "frozen/diagnostics.json").write_text(json.dumps({"screening": {"rhat_strict_upper": 1.01}}))
        (root / "frozen/trace.png").write_bytes(b"fixture-image")
        (root / "build/texas/figures/trace.png").write_bytes(b"fixture-image")
        (root / "frozen/table.csv").write_text("value\n29\n")
        (root / "build/texas/audit/table.csv").write_text("value\n29\n")
        (root / "frozen/results.json").write_text(json.dumps(raw))
        (root / "build/results.json").write_text(json.dumps({state: raw}))
        frozen = {"state": state, "status": "primary_convergence_frozen", "manifest": "frozen/manifest.json",
                  "audit_dir": "frozen", "figures_dir": "frozen", "checksums": {"frozen/table.csv": sha(root / "frozen/table.csv")}}
        (root / "frozen/freeze_manifest.json").write_text(json.dumps(frozen))
        return raw

    def test_texas_is_exported_from_registry_without_fixed_values(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            raw = self.make_fixture(root)
            result = export(root / "build", {"texas": "frozen/freeze_manifest.json"}, root / "paper", root)
            self.assertEqual(result["texas"], raw)
            self.assertEqual(result["_paper"]["texas"]["recorded_states"], 17)
            self.assertEqual(result["_paper"]["texas"]["groups"]["fixture"]["initial_democratic_majority_districts"], 4)
            self.assertTrue((root / "paper/figures/texas/trace.png").exists())
            self.assertTrue((root / "paper/tables/texas/primary_diagnostics.csv").exists())
            self.assertNotIn(b"\r", (root / "paper/tables/texas/primary_diagnostics.csv").read_bytes())

    def test_missing_figure_stops_export(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_fixture(root)
            (root / "build/texas/figures/trace.png").unlink()
            with self.assertRaises(ValueError):
                export(root / "build", {"texas": "frozen/freeze_manifest.json"}, root / "paper", root)

    def test_unfrozen_state_is_rejected(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_fixture(root)
            path = root / "frozen/freeze_manifest.json"
            value = json.loads(path.read_text())
            value["status"] = "running"
            path.write_text(json.dumps(value))
            with self.assertRaises(ValueError):
                export(root / "build", {"texas": "frozen/freeze_manifest.json"}, root / "paper", root)


if __name__ == "__main__":
    unittest.main()
