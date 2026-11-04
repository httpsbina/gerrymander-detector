"""A prefix comparison cannot discard extra states or trigger a freeze."""

import copy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from src.chain.run_texas_shared_prefix import execute, first_joint_target, prefix_manifest


def manifests(baseline=46000, dispersed=33000):
    return {key: {"source_code": {}, "experiments": {key: {"steps": steps}}}
            for key, steps in (("tx_rebuild", baseline), ("tx_dispersed", dispersed))}


class SharedPrefixTests(unittest.TestCase):
    def test_prefix_preserves_continuation_lengths(self):
        values = manifests(dispersed=45000)
        original = copy.deepcopy(values)
        view = prefix_manifest(values, 45000)
        self.assertEqual({e["steps"] for e in view["experiments"].values()}, {45000})
        self.assertEqual(values, original)
        self.assertEqual(first_joint_target(values, 45000), 50000)

    def test_prefix_rejects_missing_observations(self):
        with self.assertRaises(ValueError):
            prefix_manifest(manifests(), 45000)

    def test_next_target_cannot_exclude_a_longer_history(self):
        self.assertEqual(first_joint_target(manifests(51000, 45000), 45000), 55000)

    @patch("src.chain.run_texas_shared_prefix.finish")
    @patch("src.chain.run_texas_shared_prefix.audit_milestone", return_value=True)
    @patch("src.chain.run_texas_shared_prefix.matched_round")
    @patch("src.chain.run_texas_shared_prefix.advance")
    def test_passing_prefix_still_resumes_from_actual_endpoint(self, advance, matched, audit, finish):
        values = manifests()
        events = []
        def catch_up(manifest, key, target, destination):
            self.assertEqual(key, "tx_dispersed")
            self.assertEqual(values["tx_rebuild"]["experiments"]["tx_rebuild"]["steps"], 46000)
            manifest["experiments"][key]["steps"] = target
            events.append("dispersed45000")
        def together(manifests, target, destination):
            self.assertEqual(manifests["tx_rebuild"]["experiments"]["tx_rebuild"]["steps"], 46000)
            self.assertEqual(target, 50000)
            for key, value in manifests.items():value["experiments"][key]["steps"] = target
            events.append("all50000")
        advance.side_effect = catch_up
        matched.side_effect = together
        with TemporaryDirectory() as directory:execute(values, Path(directory))
        self.assertEqual(events, ["dispersed45000", "all50000"])
        self.assertEqual(audit.call_count, 2)
        self.assertEqual(finish.call_args.args[-1], 50000)


if __name__ == "__main__":
    unittest.main()
