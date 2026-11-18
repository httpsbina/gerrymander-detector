"""Population-distance and paired-correlation checks on synthetic fixtures."""

import unittest
import numpy as np
from paper.parallel_analysis import radial_statistics, association


class ParallelAnalysisTests(unittest.TestCase):
    def test_mean_variance_and_reciprocal(self):
        points = np.array([[0., 0.], [2., 0.], [3., 0.], [10., 0.], [12., 0.], [13., 0.]])
        population = np.ones(6)
        labels = np.array([1, 1, 1, 2, 2, 2])
        result, districts = radial_statistics(points, population, labels)
        distance = np.array([5 / 3, 1 / 3, 4 / 3] * 2)
        self.assertAlmostEqual(result['mean_distance_km'] * 1000, distance.mean())
        self.assertAlmostEqual(result['sd_distance_km'] * 1000, distance.std())
        self.assertAlmostEqual(result['distance_cv'] * result['inverse_distance_cv'], 1)
        self.assertAlmostEqual(result['rms_distance_km'] ** 2, result['mean_distance_km'] ** 2 + result['sd_distance_km'] ** 2)

    def test_weighting_matches_repeated_residents(self):
        points = np.array([[0., 0.], [2., 0.], [3., 0.], [10., 0.], [12., 0.], [13., 0.]])
        weights = np.array([1, 2, 3, 1, 2, 3])
        labels = np.array([1, 1, 1, 2, 2, 2])
        weighted, _ = radial_statistics(points, weights, labels)
        expanded, _ = radial_statistics(np.repeat(points, weights, axis=0), np.ones(weights.sum()), np.repeat(labels, weights))
        for key in weighted:
            self.assertAlmostEqual(weighted[key], expanded[key])

    def test_scale_translation_and_zero_population(self):
        points = np.array([[0., 0.], [2., 0.], [3., 0.], [10., 0.], [12., 0.], [13., 0.]])
        labels = [1, 1, 1, 2, 2, 2]
        original, _ = radial_statistics(points, np.ones(6), labels)
        moved, _ = radial_statistics(points * 4 + 20, np.ones(6), labels)
        zero, _ = radial_statistics(np.vstack([points, [1000, 1000]]), np.array([1, 1, 1, 1, 1, 1, 0]), labels + [1])
        self.assertAlmostEqual(moved['distance_cv'], original['distance_cv'])
        self.assertAlmostEqual(moved['mean_distance_km'], 4 * original['mean_distance_km'])
        for key in original:
            self.assertAlmostEqual(original[key], zero[key])

    def test_constant_radius_has_undefined_inverse(self):
        result, _ = radial_statistics([[-1, 0], [1, 0]], [1, 1], [1, 1])
        self.assertEqual(result['distance_cv'], 0)
        self.assertIsNone(result['inverse_distance_cv'])

    def test_missing_district_and_negative_population_rejected(self):
        with self.assertRaises(ValueError):
            radial_statistics([[0, 0], [1, 0]], [1, 1], [1, 3])
        with self.assertRaises(ValueError):
            radial_statistics([[0, 0], [1, 0]], [-1, 2], [1, 1])

    def test_constant_association_is_unavailable(self):
        self.assertEqual(association([1, 1, 1], [1, 2, 3])['status'], 'unavailable_constant_series')
        self.assertAlmostEqual(association([1, 2, 3], [3, 2, 1])['spearman'], -1)

    def test_independent_tally_uses_strict_majorities_and_preserves_zero_vote_units(self):
        from paper.check_parallel_comparison import independent_election_tally
        votes = np.array([[[6, 3], [1, 5]], [[1, 4], [10, 2]], [[4, 1], [2, 7]], [[3, 1], [1, 5]]])
        self.assertEqual(independent_election_tally(votes, [1, 1, 2, 2], 2), [1, 1])
        expanded = np.concatenate([votes, np.zeros((1, 2, 2), dtype=int)])
        self.assertEqual(independent_election_tally(expanded, [1, 1, 2, 2, 1], 2), [1, 1])
        self.assertEqual(independent_election_tally(votes, [2, 2, 1, 1], 2), [1, 1])

    def test_independent_tally_rejects_missing_district(self):
        from paper.check_parallel_comparison import independent_election_tally
        with self.assertRaises(ValueError):
            independent_election_tally(np.ones((2, 1, 2)), [1, 3], 3)

    def test_full_history_tail_is_not_replaced_by_checkpoint_tail(self):
        import pandas as pd
        from paper.parallel_report import summaries
        result = {'full_frozen_histories': [{'state': state, 'retained_states': 4, 'seat_sum': 4, 'seat_counts': {'0': 1, '1': 2, '2': 1}} for state in ['tx', 'nc']], 'enacted_presidential_seats': {'tx': {'2025': 0}, 'nc': {'2023': 0, '2025': 0}}}
        table = pd.DataFrame([{'state': state, 'group': 'fixture', 'step': step, 'democratic_seats_2024_presidential_model': value} for state in ['tx', 'nc'] for step, value in [(599, 1), (699, 2)]])
        elections = table.assign(President=table.democratic_seats_2024_presidential_model)
        source = {'results': {state: {'models': [{'office': 'President'}], 'enacted_seats': {'2025': [0]}} for state in ['tx', 'nc']}}
        full, _ = summaries(result, table, elections, source)
        original = next(row for row in full if row['state'] == 'tx' and row['scope'] == 'full_retained_history')
        checkpoints = next(row for row in full if row['state'] == 'tx' and row['scope'] == 'saved_postwarmup_checkpoints')
        self.assertEqual((original['observations'], original['at_or_below_enacted']), (4, 1))
        self.assertEqual((checkpoints['observations'], checkpoints['at_or_below_enacted']), (2, 0))

    def test_election_specific_enacted_score_is_preserved(self):
        import pandas as pd
        from paper.parallel_report import summaries
        result = {'full_frozen_histories': [{'state': state, 'retained_states': 4, 'seat_sum': 4, 'seat_counts': {'0': 1, '1': 2, '2': 1}} for state in ['tx', 'nc']], 'enacted_presidential_seats': {'tx': {'2025': 0}, 'nc': {'2023': 0}}}
        table = pd.DataFrame([{'state': state, 'group': 'fixture', 'step': step, 'democratic_seats_2024_presidential_model': value} for state in ['tx', 'nc'] for step, value in [(599, 1), (699, 2)]])
        elections = table.assign(President=table.democratic_seats_2024_presidential_model, Governor=[3, 5, 3, 5])
        source = {'results': {state: {'models': [{'office': 'President'}, {'office': 'Governor'}], 'enacted_seats': {'2025': [0, 4]}} for state in ['tx', 'nc']}}
        _, summary = summaries(result, table, elections, source)
        governor = next(row for row in summary if row['state'] == 'nc' and row['cohort'] == 'joint' and row['election'] == 'Governor')
        self.assertEqual(governor['enacted_seats'], 4)
        self.assertEqual(governor['mean_democratic_seats'], 4)
        self.assertEqual(governor['at_or_below_enacted'], 1)
