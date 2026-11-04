"""Paper derivations retain observations, zero counts and source fingerprints."""

import copy
import csv
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from paper.texas_outputs import collect, sha, artifacts
from paper.export import main

METRICS = ("dem_seats", "efficiency_gap", "cut_edges", "mean_median")


def fixture(root):
    (root / "paper/audits").mkdir(parents=True)
    (root / "chains").mkdir()
    (root / "dataset.bin").write_bytes(b"test fixture, not research geometry")
    def write(name, value):
        path = root / name
        path.write_text(json.dumps(value))
        return {"path": name, "sha256": sha(path)}
    manifest = {"source_code": {}, "experiments": {}}
    report = {"experiments": {}, "screening": {"rhat_strict_upper": 1.01}}
    sequences = {"tx_rebuild": {101: [2, 2, 3, 1, 2], 102: [3, 1, 1, 2, 2]},
                 "tx_dispersed": {201: [1, 2, 1, 3, 1], 202: [2, 3, 3, 3, 3]}}
    def entry(threshold):
        return {"integrity": "pass", "diagnostics": {metric: {"rank_split_rhat": 1.002,
                "bulk_ess": 1000, "tail_ess": 1100, "ess_screening_minimum": threshold,
                "all_finite": True, "mcse_mean": .1, "mcse_sd": .1, "mcse_q05": .1, "mcse_q95": .1,
                "screening_flags": []} for metric in METRICS}}
    for key, chains in sequences.items():
        manifest["experiments"][key] = {"seeds": list(chains), "steps": 5, "warmup": 1,
            "dataset": "dataset.bin", "dataset_sha256": sha(root / "dataset.bin"), "epsilon": .001,
            "node_repeats": 2, "districts": 3}
        report["experiments"][key] = entry(400)
        report["experiments"][key].update(files=[], checkpoints=[])
        for seed, seats in chains.items():
            name = f"chains/{key}_chain_eps0p001_seed{seed}_steps000000-000004.csv"
            with (root / name).open("w", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=["seed", "step", "epsilon", *METRICS, "max_abs_pop_dev"])
                writer.writeheader()
                for step, score in enumerate(seats):
                    writer.writerow({"seed": seed, "step": step, "epsilon": .001, "dem_seats": score,
                                     "efficiency_gap": .01, "cut_edges": 7, "mean_median": .02, "max_abs_pop_dev": .0001})
            report["experiments"][key]["files"].append({"path": name, "sha256": sha(root / name)})
            cp = root / f"chains/checkpoint_seed{seed}_next5.pkl"
            cp.write_bytes(b"fixture checkpoint fingerprint only")
            report["experiments"][key]["checkpoints"].append({"path": str(cp.relative_to(root)), "sha256": sha(cp)})
    original_manifest = write("execution_manifest.json", manifest)
    copied_manifest = write("paper/audits/manifest.json", manifest)
    copied_manifest.update(source_path=original_manifest["path"], source_sha256=original_manifest["sha256"])
    report["manifest_sha256"] = original_manifest["sha256"]
    report["joint_texas"] = entry(800)
    original_report = write("execution_audit.json", report)
    copied_report = write("paper/audits/audit.json", report)
    copied_report.update(source_path=original_report["path"], source_sha256=original_report["sha256"])
    score = {"plans": {"fixture": {"dem_modeled_seats": 2, "districts": [
        {"dem_modeled_votes": 2, "rep_modeled_votes": 1},
        {"dem_modeled_votes": 3, "rep_modeled_votes": 1},
        {"dem_modeled_votes": 1, "rep_modeled_votes": 3}]}}}
    score_ref = write("paper/audits/score.json", score)
    registry = {"selected": {"manifest": copied_manifest, "audit": copied_report},
                "historical_audits": [copied_report], "prefix_comparisons": [],
                "enacted_block_score": score_ref, "enacted_score_pointer": ["plans", "fixture", "dem_modeled_seats"],
                "plan_label": "Fixture plan"}
    write("paper/texas_audits.json", registry)
    return root / "paper/texas_audits.json"


class TexasPaperTests(unittest.TestCase):
    def test_score_is_read_from_audit_and_zero_chain_is_kept(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            data = collect(fixture(root), root)
            self.assertEqual(data["enacted_democratic_seats"], 2)
            self.assertEqual(next(r for r in data["tail_counts"] if r["seed"] == 202)["states_at_or_below_score"], 0)
            self.assertEqual(data["tail_counts"][-1]["retained_states"], 16)
            self.assertEqual(data["tail_counts"][-1]["states_at_or_below_score"], 10)
            self.assertEqual(data["groups"]["tx_rebuild"]["mean_democratic_seats"], 1.75)
            self.assertEqual(data["groups"]["tx_dispersed"]["mean_democratic_seats"], 2.375)
            self.assertEqual(sum(data["groups"]["tx_rebuild"]["histogram"].values()), 8)
            self.assertEqual(len(data["diagnostic_history"]), 12)

    def test_changed_trace_is_rejected(self):
        with TemporaryDirectory() as directory:
            root = Path(directory);registry = fixture(root)
            path = next((root / "chains").glob("*.csv"))
            path.write_text(path.read_text().replace(".001", ".002"))
            with self.assertRaisesRegex(ValueError, "input changed"):
                collect(registry, root)

    def test_registered_copy_cannot_change_execution_values(self):
        with TemporaryDirectory() as directory:
            root = Path(directory);registry = fixture(root)
            path = root / "paper/audits/manifest.json";value = json.loads(path.read_text())
            value["experiments"]["tx_rebuild"]["warmup"] = 2;path.write_text(json.dumps(value))
            reg = json.loads(registry.read_text());reg["selected"]["manifest"]["sha256"] = sha(path);registry.write_text(json.dumps(reg))
            with self.assertRaisesRegex(ValueError, "differs from its execution source"):
                collect(registry, root)

    def test_frozen_selection_uses_same_derivations(self):
        with TemporaryDirectory() as directory:
            root = Path(directory);registry = fixture(root)
            selected = {"manifest": {"path": "execution_manifest.json", "sha256": sha(root / "execution_manifest.json")},
                        "audit": {"path": "execution_audit.json", "sha256": sha(root / "execution_audit.json")}}
            provisional = collect(registry, root)
            frozen = collect(registry, root, selected, frozen=True)
            self.assertEqual(frozen["status"], "frozen")
            for key in ("tail_counts", "groups", "selected_diagnostics"):
                self.assertEqual(provisional[key], frozen[key])
            outputs = artifacts(frozen)
            self.assertIn("figures/texas/seat_histogram.png", outputs)
            self.assertIn("tables/texas/shared_diagnostics.csv", outputs)
            self.assertNotIn(b"Provisional", outputs["texas_findings.md"])

    @patch("paper.export.export")
    @patch("paper.export.export_provisional_texas")
    @patch("paper.export.subprocess.run")
    def test_same_cli_switches_to_frozen_registry(self, run, provisional, frozen):
        with TemporaryDirectory() as directory:
            root = Path(directory);(root / "configs").mkdir()
            (root / "configs/paper_freezes.json").write_text(json.dumps({"texas": "frozen.json"}))
            with patch("paper.export.ROOT", root), patch("sys.argv", ["paper.export", "--texas", "--source-root", str(root),
                       "--registry", str(root / "configs/paper_freezes.json"), "--output-dir", str(root / "paper")]):
                main()
            provisional.assert_not_called()
            frozen.assert_called_once()
            self.assertEqual(frozen.call_args.args[1], {"texas": "frozen.json"})


if __name__ == "__main__":
    unittest.main()
