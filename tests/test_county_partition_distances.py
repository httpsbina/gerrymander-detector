"""County coverage and selection checks on synthetic unit records."""

import unittest

from src.analysis.audit_county_partition_distances import county_masks


class CountySelectionTests(unittest.TestCase):
    def test_selection_uses_total_population_and_includes_zero_population_units(self):
        coverage, masks = county_masks(["A", "B", "A", "B"], [500000, 2, 0, 3], 500000)
        self.assertEqual(set(masks), {"A"})
        self.assertEqual(masks["A"].tolist(), [True, False, True, False])
        self.assertEqual(coverage[0]["units"], 2)
        self.assertEqual(coverage[0]["zero_population_units"], 1)
        self.assertFalse(coverage[1]["selected"])

    def test_below_threshold_counties_remain_in_coverage_record(self):
        coverage, masks = county_masks(["A", "B"], [4, 6], 10)
        self.assertEqual(masks, {})
        self.assertEqual(len(coverage), 2)
        self.assertEqual(sum(row["population"] for row in coverage), 10)

    def test_invalid_coverage_population_and_threshold_fail(self):
        for counties, population, minimum in ((["A"], [1, 2], 1),
                                              ([None], [1], 1),
                                              ([""], [1], 1),
                                              (["A"], [-1], 1),
                                              (["A"], [float("nan")], 1),
                                              (["A"], [1], 0)):
            with self.subTest(counties=counties, population=population, minimum=minimum), self.assertRaises(ValueError):
                county_masks(counties, population, minimum)
