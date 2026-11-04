"""Responsiveness plot inputs use the retained checkpoint observations."""

import copy
import unittest

from paper.responsiveness import values


def fixture():
    result = {"results": {"tx": {"models": [{"office": "Fixture", "columns": ["D", "R"]}],
        "inventory": {"statewide_votes": {"D": 60, "R": 40}}, "enacted_seats": {"2025": [2]},
        "groups": {"fixture": {"chains": [{"seed": 1, "checkpoints": 4}]}}}}}
    scores = [{"state": "tx", "group": "fixture", "seed": 1, "step": step, "Fixture": seat}
              for step, seat in zip([599, 699, 799, 899], [0, 1, 1, 3])]
    return result, scores


class ResponsivenessTests(unittest.TestCase):
    def test_share_range_median_and_revisited_states(self):
        result, scores = fixture()
        row = values(result, scores)["tx"][0]
        self.assertEqual(row["statewide_democratic_two_party_share"], .6)
        self.assertEqual(row["checkpoint_observations"], 4)
        self.assertEqual((row["neutral_minimum_seats"], row["neutral_median_seats"], row["neutral_maximum_seats"]), (0, 1, 3))
        self.assertEqual(row["enacted_seats"], {"2025": 2})

    def test_missing_checkpoint_rejected(self):
        result, scores = fixture()
        with self.assertRaisesRegex(ValueError, "coverage"):
            values(result, scores[:-1])

    def test_duplicate_checkpoint_rejected(self):
        result, scores = fixture(); scores[-1] = copy.deepcopy(scores[0])
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            values(result, scores)

    def test_empty_vote_total_rejected(self):
        result, scores = fixture(); result["results"]["tx"]["inventory"]["statewide_votes"] = {"D": 0, "R": 0}
        with self.assertRaisesRegex(ValueError, "vote totals"):
            values(result, scores)
