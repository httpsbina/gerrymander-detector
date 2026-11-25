"""Keep every configured field and the existing convergence minima."""
import unittest

from paper.geographic_continue import GEOGRAPHIC, passes


def values(ess=900):
    return {metric: {name: {'status': 'finite', 'value': number}
                     for name, number in [('rhat', 1.001), ('bulk_ess', ess), ('tail_ess', ess), ('mcse_mean', .01)]}
            for metric in GEOGRAPHIC}


class GeographicScreenTests(unittest.TestCase):
    def test_all_fields_pass_at_existing_joint_threshold(self):
        self.assertTrue(passes(values(800), 8))
        self.assertTrue(passes(values(600), 6))
        self.assertTrue(passes(values(400), 3))

    def test_single_chain_cannot_pass_a_cohort_screen(self):
        self.assertFalse(passes(values(), 1))

    def test_joint_minimum_does_not_use_cohort_minimum(self):
        self.assertFalse(passes(values(799.9), 8))
        self.assertFalse(passes(values(599.9), 6))
        self.assertFalse(passes(values(399.9), 4))

    def test_rhat_boundary_is_strict(self):
        v = values()
        v['mean_distance_km']['rhat']['value'] = 1.01
        self.assertFalse(passes(v, 8))

    def test_missing_metric_never_passes(self):
        v = values()
        del v['silhouette']
        self.assertFalse(passes(v, 8))

    def test_nonfinite_or_failed_diagnostic_never_passes(self):
        for field in ['rhat', 'bulk_ess', 'tail_ess', 'mcse_mean']:
            for bad in [None, float('nan'), float('inf')]:
                v = values()
                v['normalized_rms_radius'][field]['value'] = bad
                self.assertFalse(passes(v, 8))
        v = values()
        v['mean_distance_km']['mcse_mean']['status'] = 'failed'
        self.assertFalse(passes(v, 8))

    def test_tail_ess_is_required_separately(self):
        v = values()
        v['distance_cv']['tail_ess']['value'] = 799
        self.assertFalse(passes(v, 8))


if __name__ == '__main__':
    unittest.main()
