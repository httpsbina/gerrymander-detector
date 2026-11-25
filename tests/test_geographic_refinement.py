"""Synthetic geometry and moment checks, separate from research inputs."""

import unittest
import numpy as np
import shapely

from paper.geographic_geometry import partition_edges
from paper.geographic_refinement import boundary_scores, moment_radius, verify_boundary_union


class GeographicRefinementTests(unittest.TestCase):
    def test_moments_match_direct_population_distances(self):
        points = np.array([[0., 0.], [1., 2.], [8., 3.], [9., 1.]])
        population = np.array([10., 20., 15., 25.])
        labels = np.array([1, 1, 2, 2])
        sx, sy = population * points[:, 0], population * points[:, 1]
        q = population * np.sum(points ** 2, axis=1)
        normalized, radii = moment_radius(population, sx, sy, q, labels)
        global_center = np.average(points, weights=population, axis=0)
        total = np.sum(population * np.sum((points - global_center) ** 2, axis=1))
        within = 0
        for group in (1, 2):
            mask = labels == group
            center = np.average(points[mask], weights=population[mask], axis=0)
            local = np.sum(population[mask] * np.sum((points[mask] - center) ** 2, axis=1))
            within += local
            self.assertAlmostEqual(radii[group - 1], np.sqrt(local / population[mask].sum()))
        self.assertAlmostEqual(normalized, np.sqrt(within / total))

    def test_common_partition_perimeter_matches_union(self):
        pieces = np.array([shapely.box(0, 0, 1, 1), shapely.box(1, 0, 2, 1), shapely.box(2, 0, 3, 1)], dtype=object)
        edges = partition_edges(pieces)
        pp, area, perimeter = boundary_scores(shapely.area(pieces), shapely.length(pieces), edges, [1, 1, 2])
        np.testing.assert_allclose(area, [2, 1])
        np.testing.assert_allclose(perimeter, [6, 4])
        np.testing.assert_allclose(pp, [2 * np.pi / 9, np.pi / 4])

    def test_point_touch_does_not_shorten_perimeter(self):
        pieces = np.array([shapely.box(0, 0, 1, 1), shapely.box(1, 1, 2, 2)], dtype=object)
        left, right, length = partition_edges(pieces)
        self.assertEqual(len(length), 0)
        pp, area, perimeter = boundary_scores(shapely.area(pieces), shapely.length(pieces), (left, right, length), [1, 1])
        self.assertAlmostEqual(perimeter[0], 8)

    def test_overlap_is_rejected_without_repair(self):
        pieces = np.array([shapely.box(0, 0, 2, 1), shapely.box(1, 0, 3, 1)], dtype=object)
        with self.assertRaisesRegex(ValueError, 'overlaps'):
            partition_edges(pieces)

    def test_missing_district_is_rejected(self):
        with self.assertRaises(ValueError):
            moment_radius(np.ones(2), np.array([0., 1.]), np.zeros(2), np.array([0., 1.]), [1, 3])

    def test_zero_population_location_has_no_distance_mass(self):
        population = np.array([1., 1., 1., 1., 0.])
        x = np.array([0., 1., 9., 10., 1000.])
        labels = np.array([1, 1, 2, 2, 1])
        result = moment_radius(population, population * x, np.zeros(5), population * x ** 2, labels)
        expected = moment_radius(population[:4], x[:4], np.zeros(4), x[:4] ** 2, labels[:4])
        np.testing.assert_allclose(result[0], expected[0])
        np.testing.assert_allclose(result[1], expected[1])

    def test_string_checkpoint_labels_validate_against_union(self):
        pieces = np.array([shapely.box(0, 0, 1, 1), shapely.box(1, 0, 2, 1), shapely.box(2, 0, 3, 1)], dtype=object)
        result = verify_boundary_union(pieces, shapely.area(pieces), shapely.length(pieces), partition_edges(pieces), np.array(['1', '1', '2']))
        self.assertEqual(result['maximum_area_relative_error'], 0)
        self.assertEqual(result['maximum_perimeter_relative_error'], 0)

    def test_hole_boundary_is_counted_until_districts_are_joined(self):
        outer = shapely.box(0, 0, 4, 4)
        inner = shapely.box(1, 1, 3, 3)
        pieces = np.array([shapely.difference(outer, inner), inner], dtype=object)
        edges = partition_edges(pieces)
        pp, area, perimeter = boundary_scores(shapely.area(pieces), shapely.length(pieces), edges, [1, 2])
        np.testing.assert_allclose(perimeter, [24, 8])
        pp, area, perimeter = boundary_scores(shapely.area(pieces), shapely.length(pieces), edges, [1, 1])
        np.testing.assert_allclose(area, [16])
        np.testing.assert_allclose(perimeter, [16])
        np.testing.assert_allclose(pp, [np.pi / 4])
