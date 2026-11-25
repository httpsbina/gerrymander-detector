"""Synthetic checks for graph and distance-resolution decompositions."""

import unittest

import numpy as np
import pandas as pd

from paper.geographic_mixing import centroid_radial, edge_partition
from paper.geographic_unit_support import split_support


class MixingAttributionTests(unittest.TestCase):
    def test_atomic_multiplicity_is_separate_from_graph_difference(self):
        # Two atoms belong to unit zero; its edge to unit one occurs twice.
        common, counts, added, removed, within = edge_partition(
            [(0, 1), (0, 2), (1, 2), (2, 3)], [0, 0, 1, 2], [(0, 1), (0, 2)])
        self.assertEqual(common, {(0, 1), (1, 2)})
        self.assertEqual(counts, {(0, 1): 2, (1, 2): 1})
        self.assertEqual(added, {(1, 2)})
        self.assertEqual(removed, {(0, 2)})
        self.assertEqual(within, 1)
        # For labels 1,2,2: native cuts=2, multiplicity excess=1,
        # measurement-only cuts=0, native-only cuts=1, recovering 2 atom cuts.
        labels = [1, 2, 2]
        actual = sum(labels[u] != labels[v] for u, v in [(0, 1), (0, 1), (1, 2)])
        self.assertEqual(actual, 2 + 1 + 0 - 1)

    def test_group_center_collapse_preserves_total_second_moment(self):
        # Population at x=0,2,4 is grouped as {0,2} and {4}.
        answer = centroid_radial([2, 1], [2, 4], [0, 0], [4, 16], [1, 1])
        self.assertAlmostEqual(answer['within_location_km2'], (2 / 3) / 1e6)
        self.assertAlmostEqual(answer['exact_rms_squared_km2'], (8 / 3) / 1e6)
        self.assertAlmostEqual(answer['centroid_rms_squared_km2'], 2 / 1e6)
        self.assertAlmostEqual(answer['mean_km'], (4 / 3) / 1000)

    def test_zero_population_groups_do_not_move_centers(self):
        a = centroid_radial([2, 1], [2, 4], [0, 0], [4, 16], [1, 1])
        b = centroid_radial([2, 1, 0], [2, 4, 0], [0, 0, 0], [4, 16, 0], [1, 1, 1])
        self.assertEqual(a, b)

    def test_translation_preserves_distances_and_within_inertia(self):
        population = np.array([2., 1.])
        sx = np.array([2., 4.])
        q = np.array([4., 16.])
        a = centroid_radial(population, sx, [0, 0], q, [1, 1])
        shift = 100
        b = centroid_radial(population, sx + population * shift, [0, 0],
                            q + 2 * shift * sx + population * shift ** 2, [1, 1])
        for key in a:
            self.assertAlmostEqual(a[key], b[key])

    def test_split_support_retains_zero_population_splits(self):
        frame = pd.DataFrame({'unit': ['a', 'a', 'a', 'b', 'b'], 'district': [1, 1, 2, 1, 2],
                              'population': [3, 4, 5, 0, 0]})
        values = split_support(frame).set_index('unit')
        self.assertEqual(values.loc['a', 'minimum_population_relabeling'], 5)
        self.assertEqual(values.loc['a', 'minimum_block_relabeling'], 1)
        self.assertEqual(values.loc['b', 'districts'], 2)
        self.assertEqual(values.loc['b', 'minimum_population_relabeling'], 0)
        self.assertEqual(values.loc['b', 'minimum_block_relabeling'], 1)

    def test_whole_unit_assignment_needs_no_relabeling(self):
        frame = pd.DataFrame({'unit': ['a', 'a', 'b'], 'district': [1, 1, 2], 'population': [4, 3, 2]})
        values = split_support(frame)
        self.assertEqual(values.minimum_population_relabeling.sum(), 0)
        self.assertEqual(values.minimum_block_relabeling.sum(), 0)


if __name__ == '__main__':
    unittest.main()
