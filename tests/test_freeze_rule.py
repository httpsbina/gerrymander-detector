"""Freeze gates must reject incomplete or failing diagnostics."""

import copy
import unittest
from unittest.mock import patch

from src.analysis.audit_rebuild_campaign import METRICS
from src.analysis.freeze_baseline import require_screens
from src.chain.run_texas_until_freeze import advance, passing


def entry(threshold=400):
    metrics = {name: {"all_finite": True, "screening_flags": [], "rank_split_rhat": 1.001,
               "bulk_ess": 1000, "tail_ess": 1000, "ess_screening_minimum": threshold,
               "mcse_mean": 0.01, "mcse_sd": 0.01, "mcse_q05": 0.01, "mcse_q95": 0.01} for name in METRICS}
    return {"integrity": "pass", "diagnostics": metrics,
            "warmup_sensitivity": {"500": copy.deepcopy(metrics)}}


class FreezeRuleTests(unittest.TestCase):
    def setUp(self):
        self.report = {"experiments": {key: entry() for key in
                       ("nc_block_union_2023", "nc_block_union_2025")},
                       "joint_nc": {"nc_block_union": entry(600)}}

    def test_joint_pass_does_not_hide_group_failure(self):
        self.report["experiments"]["nc_block_union_2023"]["diagnostics"]["mean_median"]["screening_flags"] = ["R-hat"]
        with self.assertRaises(ValueError):
            require_screens(self.report, "nc")

    def test_all_groups_pass(self):
        self.assertEqual(len(require_screens(self.report, "nc")), 3)

    def test_missing_metric_blocks_freeze(self):
        del self.report["joint_nc"]["nc_block_union"]["diagnostics"]["cut_edges"]
        with self.assertRaises(ValueError):
            require_screens(self.report, "nc")

    def test_nonfinite_warmup_blocks_freeze(self):
        self.report["joint_nc"]["nc_block_union"]["warmup_sensitivity"]["500"]["dem_seats"]["all_finite"] = False
        with self.assertRaises(ValueError):
            require_screens(self.report, "nc")

    def test_nonfinite_primary_is_not_a_pass(self):
        value = entry()
        value["diagnostics"]["dem_seats"]["all_finite"] = False
        self.assertFalse(passing(value))

    def test_empty_flags_cannot_hide_failed_numbers(self):
        self.report["joint_nc"]["nc_block_union"]["diagnostics"]["dem_seats"]["rank_split_rhat"] = 1.02
        with self.assertRaises(ValueError):
            require_screens(self.report, "nc")

    @patch("src.chain.run_texas_until_freeze.audit_milestone")
    @patch("src.chain.run_texas_until_freeze.run_wave")
    def test_continuation_reaches_exact_milestone_in_protected_segments(self, run, audit):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        manifest = {"experiments": {"tx_rebuild": {"steps": 14400, "seeds": [11, 22]}}}
        with TemporaryDirectory() as directory:
            advance(manifest, "tx_rebuild", 15000, Path(directory))
        self.assertEqual(manifest["experiments"]["tx_rebuild"]["steps"], 15000)
        self.assertEqual(run.call_args.args[1], [("tx_rebuild", 11, 600), ("tx_rebuild", 22, 600)])
        audit.assert_called_once()


if __name__ == "__main__":
    unittest.main()
