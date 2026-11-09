"""Precision-review fixtures are separate from frozen research observations."""

import json
import math
import unittest

import numpy as np

from paper.review_precision import finite_call, half_comparison, independent_difference, tail_diagnostics
from paper.precision_report import cumulative_window_points


class PrecisionReviewTests(unittest.TestCase):
    def test_short_final_window_is_weighted_by_its_state_count(self):
        windows = [{"experiment": "fixture", "seed": 1, "first_step": 500, "last_step": 1499, "states": 1000, "dem_seats_mean": 0},
                   {"experiment": "fixture", "seed": 1, "first_step": 1500, "last_step": 1999, "states": 500, "dem_seats_mean": 6}]
        states, means = cumulative_window_points(windows, "fixture", 1, "dem_seats")
        self.assertEqual(states, [1500, 2000])
        self.assertEqual(means, [0, 2])

    def test_window_gap_is_rejected(self):
        windows = [{"experiment": "fixture", "seed": 1, "first_step": 0, "last_step": 3, "states": 4, "dem_seats_mean": 1},
                   {"experiment": "fixture", "seed": 1, "first_step": 5, "last_step": 8, "states": 4, "dem_seats_mean": 1}]
        with self.assertRaisesRegex(ValueError, "Missing"):
            cumulative_window_points(windows, "fixture", 1, "dem_seats")

    def test_odd_length_halves_keep_every_observation(self):
        samples = np.array([np.arange(9), np.arange(9) + 1])
        result = half_comparison(samples)
        self.assertEqual((result["first_states_per_chain"], result["second_states_per_chain"]), (4, 5))
        combined = (4 * result["first_mean"] + 5 * result["second_mean"]) / 9
        self.assertEqual(combined, float(samples.mean()))

    def test_independent_cohort_uncertainty_uses_both_mcse_values(self):
        result = independent_difference(10, 15, 3, 4)
        self.assertEqual(result["second_minus_first"], 5)
        self.assertEqual(result["combined_mcse"], 5)
        self.assertEqual(result["difference_over_combined_mcse"], 1)

    def test_nonfinite_calculation_is_recorded_without_nan_json(self):
        result = finite_call(lambda: float("nan"))
        self.assertEqual(result["status"], "nonfinite")
        self.assertIsNone(result["value"])
        json.dumps(result, allow_nan=False)

    def test_failed_calculation_is_recorded(self):
        def fail(): raise ArithmeticError("fixture")
        result = finite_call(fail)
        self.assertEqual(result["status"], "failed")
        self.assertIn("ArithmeticError", result["error"])

    def test_zero_events_do_not_produce_zero_uncertainty(self):
        result = tail_diagnostics(np.full((2, 20), 5), 2)
        self.assertEqual(result["events"], 0)
        self.assertEqual(result["constant_chain_indices"], [0, 1])
        self.assertIsNone(result["mcse_frequency"]["value"])
        self.assertEqual(result["mcse_frequency"]["status"], "unavailable_constant_indicator")

    def test_tail_runs_retain_repeated_states_and_zero_event_chains(self):
        samples = np.array([[2, 2, 4, 2, 4, 4, 4, 4], [4] * 8])
        result = tail_diagnostics(samples, 2)
        self.assertEqual(result["events_by_chain"], [3, 0])
        self.assertEqual(result["event_runs_by_chain"], [2, 0])
        self.assertEqual(result["observations"], 16)
        self.assertEqual(result["constant_chain_indices"], [1])
