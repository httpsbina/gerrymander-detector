"""Check geographic weighting results and retain all configured warmup comparisons."""

import argparse
import json
from pathlib import Path

import arviz as az
import geopandas as gpd
import numpy as np
import pandas as pd

from paper.compactness_mechanisms import METRICS
from paper.geographic_clustering import sha
from paper.geographic_geometry import block_master
from paper.review_precision import finite_call



def check_county_distances(root, cache, directory):
    target = directory / 'county_distance_verification.json'
    if target.exists():
        raise FileExistsError(target)
    table = pd.read_csv(directory / 'county_resident_distances.csv', dtype={'county_fips': str})
    checked, errors = 0, []
    for state in ('tx', 'nc'):
        master, _ = block_master(root, state)
        data = np.load(cache / f'{state}_points.npz')
        points = data['coordinates']
        if not np.array_equal(data['geoids'], master.GEOID20.to_numpy()):
            raise ValueError('Block coordinate identity differs')
        population = master.TOTPOP.to_numpy(dtype=float)
        center = np.average(points, weights=population, axis=0)
        total = float(np.sum(population * np.sum((points - center) ** 2, axis=1)))
        for year in ([2025] if state == 'tx' else [2023, 2025]):
            labels = master[f'DISTRICT_{year}'].to_numpy(dtype=int)
            weights = np.bincount(labels, weights=population)
            centers = np.column_stack([np.divide(np.bincount(labels, weights=population * points[:, axis]), weights, out=np.zeros_like(weights), where=weights > 0) for axis in (0, 1)])
            squared = np.sum((points - centers[labels]) ** 2, axis=1)
            direct = pd.DataFrame({'county_fips': master.GEOID20.str[:5], 'ss': population * squared, 'population': population}).groupby('county_fips').sum()
            expected = table[(table.state == state) & (table.cohort == 'joint') & (table.enacted == f'enacted_{year}')].set_index('county_fips')
            actual = np.sqrt(direct.ss / direct.population) / 1000
            values = expected.loc[actual.index, 'enacted_rms_distance_km']
            if not np.allclose(actual.to_numpy(), values.to_numpy(), rtol=1e-10, atol=1e-8):
                raise ValueError('Direct block-level county distance differs')
            errors.extend(np.abs(actual.to_numpy() - values.to_numpy()).tolist())
            checked += len(actual)
        selected = table[table.state == state]
        recovered = selected.pooled_ensemble_rms_distance_km ** 2 * 1e6 * selected.population / total
        if not np.allclose(recovered, selected.ensemble_contribution, rtol=1e-10, atol=1e-12):
            raise ValueError('Pooled ensemble RMS transformation differs')
    record = {'direct_block_level_county_comparisons': checked, 'maximum_absolute_error_km': max(errors), 'pooled_distance_transformation_checks': len(table), 'source_county_distances_sha256': sha(directory / 'county_resident_distances.csv')}
    target.write_text(json.dumps(record, indent=2, allow_nan=False) + '\n')
    print(json.dumps(record, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--review-dir', type=Path, required=True)
    parser.add_argument('--measurement-cache', type=Path)
    parser.add_argument('--county-distances-only', action='store_true')
    args = parser.parse_args()
    if args.county_distances_only:
        if args.measurement_cache is None:
            parser.error('--county-distances-only requires --measurement-cache')
        check_county_distances(args.source_root.resolve(), args.measurement_cache, args.review_dir)
        return
    output, root = args.review_dir, args.source_root.resolve()
    target = output / 'verification.json'
    if target.exists():
        raise FileExistsError(target)
    result = json.loads((output / 'results.json').read_text())
    for relative, expected in result['input_checksums'].items():
        if sha(root / relative) != expected:
            raise ValueError(f'Changed research input: {relative}')
    table = pd.read_csv(output / 'scores.csv')
    county = pd.read_csv(output / 'county_contributions.csv')
    half = pd.read_csv(output / 'county_half_shifts.csv')
    finite_columns = [*METRICS, 'silhouette', 'normalized_rms_radius', 'mean_polsby_popper']
    if not np.isfinite(table[finite_columns].to_numpy()).all():
        raise ValueError('Nonfinite measurement')
    for (state, cohort, enacted), values in county.groupby(['state', 'cohort', 'enacted']):
        selected = table[(table.state == state) & (~table.group.str.startswith('enacted')) & (table.step >= 500)]
        if cohort != 'joint':
            selected = selected[selected.group == cohort]
        expected = float((selected.normalized_rms_radius ** 2).mean())
        actual = float(values.ensemble_contribution.sum())
        reference = table[(table.state == state) & (table.group == enacted)].normalized_rms_radius.item() ** 2
        if not np.isclose(actual, expected, rtol=1e-11, atol=1e-12) or not np.isclose(values.enacted_contribution.sum(), reference, rtol=1e-11, atol=1e-12):
            raise ValueError('County aggregate identity failed')
    for (state, cohort, seed), values in half.groupby(['state', 'cohort', 'seed']):
        chain = table[(table.state == state) & (table.group == cohort) & (table.seed == seed) & (table.step >= 500)].sort_values('step')
        x = chain.normalized_rms_radius.to_numpy() ** 2
        split = len(x) // 2
        if not np.isclose(values.second_minus_first.sum(), x[split:].mean() - x[:split].mean(), rtol=1e-10, atol=1e-12):
            raise ValueError('County half-history attribution failed')
    warmups = []
    for state, subset in table[~table.group.str.startswith('enacted')].groupby('state'):
        for cohort in ['joint', *sorted(subset.group.unique())]:
            values = subset if cohort == 'joint' else subset[subset.group == cohort]
            for warmup in (0, 250, 500, 1000):
                for metric in METRICS:
                    samples = np.stack([chain.sort_values('step')[metric].to_numpy() for _, chain in values[values.step >= warmup].groupby(['group', 'seed'])])
                    warmups.append({'state': state, 'cohort': cohort, 'warmup': warmup, 'metric': metric, 'mean': float(samples.mean()), 'checkpoints_per_chain': samples.shape[1], 'rhat': finite_call(lambda: az.rhat(samples, method='rank')), 'bulk_ess': finite_call(lambda: az.ess(samples, method='bulk')), 'tail_ess': finite_call(lambda: az.ess(samples, method='tail'))})
    (output / 'warmup_sensitivity.json').write_text(json.dumps(warmups, indent=2, allow_nan=False) + '\n')
    main_diagnostics = [item[key] for item in result['diagnostics'] for key in ['rhat', 'bulk_ess', 'tail_ess', 'mcse_mean']]
    warmup_diagnostics = [item[key] for item in warmups for key in ['rhat', 'bulk_ess', 'tail_ess']]
    record = {'input_hashes_checked': len(result['input_checksums']), 'checkpoint_measurements': len(table) - 3, 'retained_checkpoint_measurements': int(((~table.group.str.startswith('enacted')) & (table.step >= 500)).sum()), 'county_identity_checks': sum(item['all_county_identities_checked'] for item in result['validation_checks']), 'main_scalar_diagnostics': len(main_diagnostics), 'warmup_scalar_diagnostics': len(warmup_diagnostics), 'unavailable_main_diagnostics': sum(item['status'] != 'finite' for item in main_diagnostics), 'unavailable_warmup_diagnostics': sum(item['status'] != 'finite' for item in warmup_diagnostics), 'sampler_sha256': sha(root / 'src/chain/run_ensemble.py'), 'checkpoint_code_sha256': sha(root / 'src/chain/checkpoint_integrity.py'), 'research_ready': False}
    target.write_text(json.dumps(record, indent=2, allow_nan=False) + '\n')
    print(json.dumps(record, indent=2))


if __name__ == '__main__':
    main()
