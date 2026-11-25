"""Geographic clustering fixtures are separate from research observations."""

import unittest
import numpy as np
from paper.geographic_clustering import scores


class GeographicClusteringTests(unittest.TestCase):
    def test_separated_clusters(self):
        points = np.array([[0, 0], [0, 1], [1, 0], [20, 0], [20, 1], [21, 0]])
        good = scores(points, [1, 1, 1, 2, 2, 2])
        bad = scores(points, [1, 2, 1, 2, 1, 2])
        self.assertGreater(good['silhouette'], 0.9)
        self.assertGreater(good['silhouette'], bad['silhouette'])
        self.assertLess(good['normalized_rms_radius'], bad['normalized_rms_radius'])

    def test_translation_rotation_scale_and_label_invariance(self):
        points = np.array([[0, 0], [0, 1], [1, 0], [20, 0], [20, 1], [21, 0]])
        original = scores(points, [1, 1, 1, 2, 2, 2])
        moved = scores(points[:, ::-1] * 7 + 30, [6, 6, 6, 4, 4, 4])
        for metric in original:
            self.assertAlmostEqual(moved[metric], original[metric])

    def test_standard_silhouette_hand_calculation(self):
        result = scores([[0, 0], [1, 0], [4, 0], [5, 0]], [1, 1, 2, 2])
        self.assertAlmostEqual(result['silhouette'], ((1 - 1 / 4.5) + (1 - 1 / 3.5)) / 2)

    def test_reject_singleton_and_one_district(self):
        with self.assertRaises(ValueError):
            scores([[0, 0], [1, 0], [2, 0]], [1, 1, 2])
        with self.assertRaises(ValueError):
            scores([[0, 0], [1, 0]], [1, 1])
