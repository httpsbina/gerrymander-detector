"""Moment and weighting tests on synthetic geometry, separate from research data."""

import unittest
import numpy as np
import shapely

from paper.compactness_mechanisms import polygon_moments
from paper.geographic_refinement import moment_radius


class CompactnessMechanismsTests(unittest.TestCase):
    def test_unit_square_integrals(self):
        result = polygon_moments(shapely.box(0, 0, 1, 1), np.zeros(2))
        np.testing.assert_allclose(result, [1, .5, .5, 2 / 3])

    def test_translation_and_orientation(self):
        polygon = shapely.box(10, 20, 11, 21)
        result = polygon_moments(polygon, np.array([10, 20]))
        reverse = polygon_moments(shapely.reverse(polygon), np.array([10, 20]))
        np.testing.assert_allclose(result, [1, .5, .5, 2 / 3])
        np.testing.assert_allclose(result, reverse)

    def test_holes_are_subtracted(self):
        polygon = shapely.difference(shapely.box(-2, -2, 2, 2), shapely.box(-1, -1, 1, 1))
        result = polygon_moments(polygon, np.zeros(2))
        np.testing.assert_allclose(result, [12, 0, 0, 40])

    def test_multipart_moments_are_additive(self):
        a, b = shapely.box(0, 0, 1, 1), shapely.box(2, 0, 3, 1)
        result = polygon_moments(shapely.MultiPolygon([a, b]), np.zeros(2))
        np.testing.assert_allclose(result, polygon_moments(a, np.zeros(2)) + polygon_moments(b, np.zeros(2)))

    def test_common_within_block_variance_preserves_radius_order(self):
        moment = np.array([polygon_moments(shapely.box(i, 0, i + 1, 1), np.zeros(2)) for i in range(4)])
        good, _ = moment_radius(*moment.T, [1, 1, 2, 2])
        bad, _ = moment_radius(*moment.T, [1, 2, 1, 2])
        self.assertLess(good, bad)
        for common_variance in [0, .01, 1, 100]:
            self.assertLess(np.sqrt((good * good + common_variance) / (1 + common_variance)), np.sqrt((bad * bad + common_variance) / (1 + common_variance)))

    def test_invalid_polygon_is_rejected(self):
        with self.assertRaises(ValueError):
            polygon_moments(shapely.Polygon([(0, 0), (1, 1), (0, 1), (1, 0)]), np.zeros(2))

    def test_county_contributions_sum_and_relabel_invariance(self):
        import pandas as pd
        from paper.compactness_mechanisms import county_contributions
        x = np.array([-3., -2., 2., 3.])
        population = np.ones(4)
        atoms = pd.DataFrame({'population': population, 'sx': x, 'sy': np.zeros(4), 'q': x * x})
        counties = np.array([0, 0, 1, 1])
        labels = np.array([1, 1, 2, 2])
        result = county_contributions(population, x, np.zeros(4), x * x, counties, np.arange(4), labels, atoms)
        radius, _ = moment_radius(population, x, np.zeros(4), x * x, labels)
        self.assertAlmostEqual(result.sum(), radius ** 2)
        flipped = county_contributions(population, x, np.zeros(4), x * x, counties, np.arange(4), 3 - labels, atoms)
        np.testing.assert_allclose(result, flipped)

    def test_refining_measurement_units_changes_count_not_boundary_length(self):
        from paper.geographic_geometry import partition_edges
        coarse = np.array([shapely.box(0, 0, 1, 2), shapely.box(1, 0, 2, 2)], dtype=object)
        fine = np.array([shapely.box(0, 0, 1, 1), shapely.box(0, 1, 1, 2), shapely.box(1, 0, 2, 1), shapely.box(1, 1, 2, 2)], dtype=object)
        left, right, length = partition_edges(coarse)
        coarse_labels = np.array([1, 2])
        selected = coarse_labels[left] != coarse_labels[right]
        self.assertEqual(int(selected.sum()), 1)
        self.assertAlmostEqual(length[selected].sum(), 2)
        left, right, length = partition_edges(fine)
        fine_labels = np.array([1, 1, 2, 2])
        selected = fine_labels[left] != fine_labels[right]
        self.assertEqual(int(selected.sum()), 2)
        self.assertAlmostEqual(length[selected].sum(), 2)
