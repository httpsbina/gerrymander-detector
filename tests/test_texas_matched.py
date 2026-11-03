"""Cohorts pause without truncation and advance together after catch-up."""

import copy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from src.chain.run_texas_matched import catch_up, cohort_passes, matched_round
from test_freeze_rule import entry


def manifests(baseline, dispersed):
    return {key: {"experiments": {key: {"steps": steps}}} for key, steps in
            (("tx_rebuild", baseline), ("tx_dispersed", dispersed))}


class MatchedScheduleTests(unittest.TestCase):
    @patch("src.chain.run_texas_matched.audit_milestone")
    @patch("src.chain.run_texas_matched.cohort_passes")
    @patch("src.chain.run_texas_matched.advance")
    def test_baseline_stops_at_first_pass_and_dispersed_catches_up(self, advance, passes, audit):
        calls = []
        def step(manifest, key, target, directory):
            calls.append((key, target))
            manifest["experiments"][key]["steps"] = target
        advance.side_effect = step
        passes.side_effect = lambda directory, key, steps: steps >= 45000
        values = manifests(43000, 29000)
        with TemporaryDirectory() as directory:
            target = catch_up(values, Path(directory) / "catch_up")
        self.assertEqual(target, 45000)
        self.assertEqual([n for key, n in calls if key == "tx_rebuild"], [45000])
        self.assertTrue(all(n <= 45000 for key, n in calls))
        self.assertEqual({m["experiments"][key]["steps"] for key, m in values.items()}, {45000})

    @patch("src.chain.run_texas_matched.audit_milestone")
    @patch("src.chain.run_texas_matched.cohort_passes", return_value=True)
    @patch("src.chain.run_texas_matched.advance")
    def test_existing_passing_boundary_is_kept(self, advance, passes, audit):
        def step(manifest, key, target, directory):
            self.assertEqual(key, "tx_dispersed")
            manifest["experiments"][key]["steps"] = target
        advance.side_effect = step
        values = manifests(45000, 40000)
        with TemporaryDirectory() as directory:
            self.assertEqual(catch_up(values, Path(directory) / "catch_up"), 45000)
        self.assertEqual(values["tx_rebuild"]["experiments"]["tx_rebuild"]["steps"], 45000)

    @patch("src.chain.run_texas_matched.advance")
    def test_failed_joint_round_extends_both_to_same_target(self, advance):
        def step(manifest, key, target, directory):
            manifest["experiments"][key]["steps"] = target
        advance.side_effect = step
        values = manifests(45000, 45000)
        with TemporaryDirectory() as directory:
            matched_round(values, 50000, Path(directory) / "matched")
        self.assertEqual(advance.call_count, 2)
        self.assertEqual({m["experiments"][key]["steps"] for key, m in values.items()}, {50000})

    def test_longer_dispersed_history_is_never_cut(self):
        values = manifests(45000, 46000)
        original = copy.deepcopy(values)
        with self.assertRaises(ValueError):
            catch_up(values, Path("unused"))
        self.assertEqual(values, original)

    def test_failed_or_missing_metric_prevents_pause(self):
        for mutation in (lambda e: e["diagnostics"].pop("cut_edges"),
                         lambda e: e["diagnostics"]["mean_median"].update(rank_split_rhat=1.01),
                         lambda e: e["diagnostics"]["dem_seats"].update(bulk_ess=399),
                         lambda e: e["diagnostics"]["dem_seats"].update(tail_ess=float("nan"))):
            value = entry()
            mutation(value)
            with TemporaryDirectory() as directory:
                path = Path(directory) / "milestone_045000/audit"
                path.mkdir(parents=True)
                (path / "diagnostics.json").write_text(json.dumps({"experiments": {"tx_rebuild": value}}))
                self.assertFalse(cohort_passes(Path(directory), "tx_rebuild", 45000))


if __name__ == "__main__":
    unittest.main()
