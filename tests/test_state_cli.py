"""Standard-library smoke tests; no GIS data or GerryChain required."""

import io
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import main  # noqa: E402


class StateCliTests(unittest.TestCase):
    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            result = main.main(list(argv))
        return result, out.getvalue(), err.getvalue()

    def test_status_is_read_only(self):
        code, out, _ = self.run_cli("--texas")
        self.assertEqual(code, 0)
        self.assertIn("DATASET EXISTS:", out)
        self.assertIn("convergence not established", out)

    def test_nc_years_are_distinct(self):
        states = main.load_registry()
        _, year23, plan23 = main.get_selection(states, "north_carolina", "2023")
        _, year25, plan25 = main.get_selection(states, "north_carolina", "2025")
        self.assertEqual((year23, year25), ("2023", "2025"))
        self.assertEqual(plan23["assignment"], "CONG_DIST")
        self.assertEqual(plan25["assignment"], "CONG_DIST_2025")

    def test_penn_blocks_execution_but_status_works(self):
        code, out, _ = self.run_cli("--penn")
        self.assertEqual(code, 0)
        self.assertIn("NOT RESEARCH-VALIDATED", out)
        code, _, err = self.run_cli("--penn", "--stage", "simulate", "--steps", "10", "--seed", "5", "--dry-run")
        self.assertEqual(code, 2)
        self.assertIn("no validated dataset", err)

    def test_texas_audit_dry_run_uses_existing_files(self):
        code, out, _ = self.run_cli("--texas", "--stage", "audit", "--dry-run")
        self.assertEqual(code, 0)
        self.assertIn("texas_independent_pilot", out)
        self.assertIn("--steps 4000", out)
        self.assertIn("--seeds 1117 2227 3331", out)

    def test_nc_simulation_dry_run_uses_selected_assignment(self):
        code, out, _ = self.run_cli(
            "--nc", "--year", "2025", "--stage", "simulate", "--seed", "1234", "--steps", "20", "--dry-run"
        )
        self.assertEqual(code, 0)
        self.assertIn("--assignment-col CONG_DIST_2025", out)
        self.assertIn("--epsilon 0.005", out)

    def test_simulation_requires_explicit_seed_and_steps(self):
        code, _, err = self.run_cli("--texas", "--stage", "simulate", "--dry-run")
        self.assertEqual(code, 2)
        self.assertIn("requires --seed", err)

    def test_checkpoint_name_matches_config(self):
        states = main.load_registry()
        state, _, plan = main.get_selection(states, "texas")
        args = main.build_parser().parse_args([
            "--texas", "--stage", "simulate", "--steps", "2000", "--seed", "1117",
            "--resume-from", "outputs/analysis/tx_independent_pilot/checkpoints/texas_independent_pilot_checkpoint_eps0p001_seed1117_next4000.pkl",
            "--dry-run",
        ])
        command, path = main.build_simulation_command(args, state, plan)
        self.assertIn("steps004000-005999.csv", str(path))
        self.assertIn("--resume-from", command)

    def test_existing_segment_cannot_be_overwritten(self):
        states = main.load_registry()
        state, _, plan = main.get_selection(states, "texas")
        args = main.build_parser().parse_args([
            "--texas", "--stage", "simulate", "--steps", "10", "--seed", "444",
            "--dry-run",
        ])
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(main, "resolve", side_effect=lambda relative: Path(tmp) / str(relative)):
                _, target = main.build_simulation_command(args, state, plan)
                target.parent.mkdir(parents=True)
                target.write_text("existing content", encoding="utf-8")
                with self.assertRaisesRegex(main.PipelineError, "Refusing to overwrite"):
                    main.build_simulation_command(args, state, plan)

    def test_dry_run_does_not_spawn_subprocess(self):
        with patch.object(subprocess, "run", side_effect=AssertionError("unexpected subprocess")):
            code, _, _ = self.run_cli("--texas", "--stage", "audit", "--dry-run")
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
