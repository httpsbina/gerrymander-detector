"""Integrity and output-protection tests using synthetic CSVs, never research data."""

import csv
import io
import json
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from unittest.mock import patch

import main
from src.analysis.research_preflight import audit_segments, local_path, write_report


class ResearchPreflightTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def segment(self, first, last, **overrides):
        path = self.root / f"fixture_steps{first:06d}-{last:06d}.csv"
        rows = []
        for step in range(first, last + 1):
            row = dict(step=step, seed=7, epsilon=0.005, dem_seats=4,
                       efficiency_gap=0.1, cut_edges=20,
                       max_abs_pop_dev=0.004, plan_hash="a" * 64)
            row.update(overrides)
            rows.append(row)
        with path.open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        return path

    def audit(self, paths):
        return audit_segments(paths, 7, 0.005, 14)

    def test_contiguous_segments_preserve_all_steps_and_hash_inputs(self):
        report = self.audit([self.segment(0, 1), self.segment(2, 4)])
        self.assertTrue(report["length_verified"])
        self.assertEqual(report["observed_unique_steps"], 5)
        self.assertEqual(report["last_step"], 4)
        self.assertEqual(len(report["files"][0]["sha256"]), 64)

    def test_gap_and_overlap_fail(self):
        for second in ((3, 4), (1, 3)):
            with self.subTest(second=second):
                report = self.audit([self.segment(0, 1), self.segment(*second)])
                self.assertFalse(report["length_verified"])
                self.assertEqual(report["status"], "fail")

    def test_nonfinite_and_parameter_mismatches_fail(self):
        for overrides in (
            {"efficiency_gap": "inf"}, {"cut_edges": "nan"},
            {"seed": 8}, {"epsilon": 0.01}, {"max_abs_pop_dev": 0.006},
            {"dem_seats": 15}, {"dem_seats": 3.5}, {"plan_hash": "bad"},
        ):
            with self.subTest(overrides=overrides):
                self.assertFalse(self.audit([self.segment(0, 1, **overrides)])["length_verified"])

    def test_short_or_missing_csv_fails(self):
        path = self.segment(0, 2)
        path.write_text(path.read_text().rsplit("\n", 2)[0] + "\n")
        self.assertFalse(self.audit([path])["length_verified"])
        self.assertFalse(self.audit([])["length_verified"])

    def test_existing_output_directory_refused_without_touching_files(self):
        destination = self.root / "report"
        destination.mkdir()
        original = destination / "report.json"
        original.write_text("preserve me")
        with self.assertRaises(FileExistsError):
            write_report({}, destination)
        self.assertEqual(original.read_text(), "preserve me")

    def test_paths_cannot_escape_checkout_through_symlink(self):
        (self.root / "escape").symlink_to(self.root.parent, target_is_directory=True)
        with self.assertRaises(ValueError):
            local_path(self.root, "escape/outside")
        with self.assertRaises(ValueError):
            local_path(self.root, "../outside")

    def test_cli_reports_missing_inputs_without_claiming_readiness(self):
        output = io.StringIO()
        with redirect_stdout(output):
            code = main.main(["--nc", "--year", "2023", "--stage", "preflight"])
        self.assertEqual(code, 0)
        report = json.loads(output.getvalue())
        self.assertFalse(report["research_ready"])
        self.assertEqual(report["starting_plan"], "2023")
        self.assertEqual(report["execution_status"], "completed")
        self.assertTrue(all(value == "unavailable" for value in report["diagnostics"].values()))

    def test_cli_dry_run_does_not_inspect_or_write(self):
        with patch("src.analysis.research_preflight.build_report", side_effect=AssertionError):
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main.main(["--texas", "--stage", "preflight", "--dry-run"]), 0)

    def test_cli_rejects_report_dir_outside_preflight(self):
        with redirect_stderr(io.StringIO()):
            self.assertEqual(main.main(["--texas", "--report-dir", "unused"]), 2)


if __name__ == "__main__":
    unittest.main()
