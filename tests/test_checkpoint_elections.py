"""Fixtures for checkpoint election scoring; no research observations."""

import unittest

import numpy as np

from paper.score_checkpoint_elections import election_fields, vote_seats


class CheckpointElectionTests(unittest.TestCase):
    def test_joint_summary_weights_checkpoint_counts(self):
        from paper.summarize_checkpoint_elections import summary_rows
        result = {"results": {"fixture": {"models": [{"office": "Fixture"}],
            "enacted_seats": {"fixture": [2]}, "groups": {
                "first": {"checkpoints": 2, "mean_democratic_seats": [1], "at_or_below_enacted": {"fixture": [2]}},
                "second": {"checkpoints": 6, "mean_democratic_seats": [3], "at_or_below_enacted": {"fixture": [0]}}}}}}
        joint = next(row for row in summary_rows(result) if row["group"] == "joint")
        self.assertEqual(joint["checkpoints"], 8)
        self.assertEqual(joint["mean_democratic_seats"], 2.5)
        self.assertEqual(joint["checkpoints_at_or_below_enacted"], 2)

    def test_assignment_fingerprint_ignores_labels_but_detects_boundary_changes(self):
        from paper.validate_checkpoint_elections import assignment_hash
        edges = [(0, 1), (1, 2), (2, 3)]
        original = assignment_hash({0: 1, 1: 1, 2: 2, 3: 2}, edges)
        self.assertEqual(original, assignment_hash({0: 7, 1: 7, 2: 9, 3: 9}, edges))
        self.assertNotEqual(original, assignment_hash({0: 1, 1: 2, 2: 2, 3: 2}, edges))

    def test_strict_majorities_and_ties(self):
        votes = np.array([[[6, 4], [5, 5]], [[3, 7], [8, 2]],
                          [[8, 2], [4, 6]], [[5, 5], [1, 9]]])
        self.assertEqual(vote_seats(votes, [1, 1, 2, 2], 2), [1, 1])

    def test_missing_district_rejected(self):
        with self.assertRaisesRegex(ValueError, "coverage"):
            vote_seats(np.ones((2, 1, 2)), [1, 1], 2)

    def test_empty_district_votes_rejected(self):
        with self.assertRaisesRegex(ValueError, "Empty"):
            vote_seats(np.zeros((2, 1, 2)), [1, 2], 2)

    def test_only_registered_statewide_elections_selected(self):
        from paper.score_checkpoint_elections import OFFICES
        fields = [prefix + party + "XXX" for prefix in OFFICES["tx"] for party in "DR"]
        fields += ["GCON01DXXX", "GCON01RXXX", "G24ACVYES"]
        models = election_fields(fields, "tx")
        self.assertEqual(len(models), 9)
        self.assertFalse(any(column.startswith("GCON") for model in models for column in model["columns"]))

    def test_ambiguous_candidate_rejected(self):
        from paper.score_checkpoint_elections import OFFICES
        fields = [prefix + party + "XXX" for prefix in OFFICES["nc"] for party in "DR"]
        fields += ["G24GOVDYYY"]
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            election_fields(fields, "nc")


if __name__ == "__main__":
    unittest.main()
