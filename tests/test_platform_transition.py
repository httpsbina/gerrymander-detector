"""Native segments may change runtime metadata, never sampling inputs."""

import copy
from pathlib import Path
import pickle
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from src.chain.benchmark_baselines import checkpoint_path
from src.chain.continue_on_target import verify_cohort
from src.chain.platform_transition import eligible_profile


def profile():
    return {"dataset_sha256": "fixture-data", "graph_sha256": "fixture-graph",
            "runner_sha256": "fixture-sampler", "checkpoint_code_sha256": "fixture-checkpoints",
            "configuration": {"epsilon": 0.001},
            "runtime": {"python": "3.12.16 fixture-build", "platform": "fixture-source",
                        "packages": {"fixture": "1.0"}}}


class PlatformTransitionTests(unittest.TestCase):
    def test_platform_and_build_changes_are_eligible(self):
        source = profile()
        target = copy.deepcopy(source)
        target["runtime"].update(python="3.12.16 fixture-other-build", platform="fixture-target")
        self.assertTrue(eligible_profile(source, target))

    def test_sampling_input_changes_are_rejected(self):
        for key in ("dataset_sha256", "graph_sha256", "runner_sha256", "checkpoint_code_sha256", "configuration"):
            source = profile()
            target = copy.deepcopy(source)
            target[key] = "changed"
            with self.subTest(key=key), self.assertRaises(ValueError):
                eligible_profile(source, target)

    def test_package_changes_are_rejected(self):
        source = profile()
        target = copy.deepcopy(source)
        target["runtime"]["packages"]["fixture"] = "2.0"
        with self.assertRaises(ValueError):
            eligible_profile(source, target)

    def test_python_release_changes_are_rejected(self):
        source = profile()
        target = copy.deepcopy(source)
        target["runtime"]["python"] = "3.13.0 fixture-build"
        with self.assertRaises(ValueError):
            eligible_profile(source, target)

    def verify_fixture(self, changed_runtime, replay_error, complete=True):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        e = {"prefix": "fixture", "epsilon": 0.001, "steps": 200, "seeds": [7], "input_dir": "old/ensembles"}
        checkpoints = root / "old/checkpoints"
        checkpoints.mkdir(parents=True)
        source = profile()
        with checkpoint_path(checkpoints, e, 7, 200).open("wb") as stream:
            pickle.dump({"provenance": source}, stream)
        runtime = copy.deepcopy(source["runtime"])
        if changed_runtime:
            runtime["platform"] = "fixture-target"
        with patch("src.chain.continue_on_target.ROOT", root), \
             patch("src.chain.continue_on_target.current_runtime", return_value=runtime), \
             patch("src.chain.continue_on_target.prepare", return_value=(copy.deepcopy(e), {"files": {}, "chains": []})), \
             patch("src.chain.continue_on_target.replay", side_effect=replay_error), \
             patch("src.chain.continue_on_target.complete_native_probe", return_value=complete):
            return verify_cohort("fixture", e, root / "new", 1, {})

    def test_complete_platform_difference_is_documented(self):
        e, records = self.verify_fixture(True, ValueError("Replay CSV differs from the original trajectory"))
        self.assertEqual(records[0]["continuation_class"], "checkpoint_state_continuation")
        self.assertEqual(records[0]["last_bitwise_source_step"], 199)
        self.assertEqual(records[0]["new_segment_first_step"], 200)
        self.assertTrue(e["platform_transitions"])

    def test_same_runtime_replay_failure_stops(self):
        with self.assertRaises(ValueError):
            self.verify_fixture(False, ValueError("Replay CSV differs from the original trajectory"))

    def test_incomplete_probe_is_not_a_platform_exception(self):
        with self.assertRaises(ValueError):
            self.verify_fixture(True, ValueError("Replay CSV differs from the original trajectory"), False)

    def test_runtime_execution_failure_is_not_waived(self):
        with self.assertRaises(RuntimeError):
            self.verify_fixture(True, RuntimeError("execution failed"))


if __name__ == "__main__":
    unittest.main()
