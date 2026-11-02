"""Reference cases for label-invariant partition comparisons."""

import unittest

import numpy as np

from src.analysis.audit_partition_distances import information_distance, partition_distances


class PartitionDistanceTests(unittest.TestCase):
    def test_relabeling_districts_has_zero_distance(self):
        unit, population = partition_distances([1, 1, 2, 2], [9, 9, 3, 3], [5, 1, 2, 0])
        self.assertAlmostEqual(unit, 0)
        self.assertAlmostEqual(population, 0)

    def test_independent_binary_partitions_have_two_bits(self):
        result = partition_distances([0, 0, 1, 1], [0, 1, 0, 1], [1, 1, 1, 1])
        np.testing.assert_allclose(result, [2, 2])

    def test_zero_population_units_remain_in_unit_measure(self):
        result = partition_distances([0, 0, 1, 1], [0, 1, 0, 1], [1, 0, 0, 1])
        np.testing.assert_allclose(result, [2, 0])

    def test_weighted_distance_is_symmetric(self):
        left, right, weights = [0, 0, 1, 1, 2], [1, 2, 2, 1, 1], [2, 3, 0, 7, 1]
        np.testing.assert_allclose(partition_distances(left, right, weights), partition_distances(right, left, weights))

    def test_missing_coverage_and_invalid_weights_fail(self):
        for weights in ([0, 0], [-1, 2], [float("nan"), 1], [1]):
            with self.subTest(weights=weights), self.assertRaises(ValueError):
                partition_distances([0, 1], [1, 0], weights)
        with self.assertRaises(ValueError):
            partition_distances([0, None], [1, 0], [1, 1])
        with self.assertRaises(ValueError):
            information_distance([[1, -1], [0, 2]])
