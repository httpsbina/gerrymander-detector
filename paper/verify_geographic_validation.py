"""Independently check the completed geographic measurements and frozen source records."""

import argparse
import ast
import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

from paper.geographic_clustering import sha
from paper.geographic_geometry import block_master


def verify(root, cache, directory):
    target = directory / 'verification.json'
    if target.exists():
        raise FileExistsError(target)
    result = json.loads((directory / 'results.json').read_text())
    for relative, expected in result['input_checksums'].items():
        if sha(root / relative) != expected:
            raise ValueError(f'Changed source: {relative}')
    table = pd.read_csv(directory / 'scores.csv')
    coverage = {}
    direct_checks = []
    unit_population_checks = []
    for state, length, chains in [('tx', 70000, 8), ('nc', 23000, 6)]:
        selected = table[(table.state == state) & (~table.group.str.startswith('enacted'))]
        coverage[state] = {'chains': selected.groupby(['group', 'seed']).ngroups, 'measurements': len(selected), 'retained': int((selected.step >= 500).sum()), 'distinct_retained_plan_hashes': int(selected[selected.step >= 500].plan_hash.nunique())}
        if coverage[state]['chains'] != chains:
            raise ValueError('Missing chains')
        for _, chain in selected.groupby(['group', 'seed']):
            if chain.sort_values('step').step.tolist() != list(range(99, length, 100)):
                raise ValueError('Missing or overlapping checkpoint measurements')
        master, _ = block_master(root, state)
        data = np.load(cache / f'{state}_points.npz')
        points = data['coordinates']
        population = master.TOTPOP.to_numpy(dtype=float)
        center = np.average(points, weights=population, axis=0)
        total = float(np.sum(population * np.sum((points - center) ** 2, axis=1)))
        for year in ([2025] if state == 'tx' else [2023, 2025]):
            within = 0
            for _, group in master.groupby(f'DISTRICT_{year}'):
                nodes = group.index.to_numpy()
                local_center = np.average(points[nodes], weights=population[nodes], axis=0)
                within += float(np.sum(population[nodes] * np.sum((points[nodes] - local_center) ** 2, axis=1)))
            actual = float(np.sqrt(within / total))
            expected = table[(table.state == state) & (table.group == f'enacted_{year}')].normalized_rms_radius.item()
            if not np.isclose(actual, expected, rtol=1e-12, atol=1e-12):
                raise ValueError('Direct population radius and moment calculation differ')
            direct_checks.append({'state': state, 'year': year, 'direct_radius': actual, 'recorded_radius': expected, 'absolute_difference': abs(actual - expected)})
        atoms = gpd.read_file(cache / f'{state}_atoms.gpkg', ignore_geometry=True)
        manifest = 'tx_shared45000_continuation_20261103/shared_070000/manifest.json' if state == 'tx' else 'nc_primary_continuation/snapshot_003/manifest.json'
        specs = json.loads((root / 'outputs/analysis/convergence_campaign_2026-11-02' / manifest).read_text())['experiments']
        for group, spec in specs.items():
            frame = gpd.read_file(root / spec['dataset'], layer='precincts', ignore_geometry=True)
            conserved = atoms.groupby('unit').population.sum().loc[frame.UNIQUE_ID].to_numpy()
            if not np.array_equal(conserved, frame.TOTPOP.to_numpy()):
                raise ValueError('Simulation unit populations differ')
            unit_population_checks.append({'group': group, 'units': len(frame), 'population': int(conserved.sum())})
    for row in result['direct_union_checks']:
        if row['maximum_area_relative_error'] > 1e-10 or row['maximum_perimeter_relative_error'] > 1e-10:
            raise ValueError('Failed union validation')
    expected_checks = 3 + 14
    if len(result['direct_union_checks']) != expected_checks:
        raise ValueError('Incomplete direct union checks')
    diagnostics = [item[key] for item in result['diagnostics'] for key in ['rhat', 'bulk_ess', 'tail_ess', 'mcse_mean']]
    if not np.isfinite(table[['silhouette', 'normalized_rms_radius', 'mean_polsby_popper', 'minimum_polsby_popper']].to_numpy()).all():
        raise ValueError('Nonfinite measurement')
    repo = Path(__file__).resolve().parents[1]
    for path in ['paper/geographic_geometry.py', 'paper/geographic_refinement.py', 'paper/geographic_validation_report.py', 'paper/verify_geographic_validation.py', 'tests/test_geographic_refinement.py']:
        ast.parse((repo / path).read_text())
    record = {'source_hashes_checked': len(result['input_checksums']), 'coverage': coverage, 'direct_population_radius_checks': direct_checks, 'unit_population_checks': unit_population_checks, 'direct_polygon_union_checks': expected_checks, 'new_scalar_diagnostics': len(diagnostics), 'nonfinite_or_unavailable_main_diagnostics': sum(item['status'] != 'finite' for item in diagnostics), 'sampler_sha256': sha(root / 'src/chain/run_ensemble.py'), 'checkpoint_code_sha256': sha(root / 'src/chain/checkpoint_integrity.py'), 'research_ready': False}
    target.write_text(json.dumps(record, indent=2, allow_nan=False) + '\n')
    print(json.dumps(record, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--measurement-cache', type=Path, required=True)
    parser.add_argument('--report-dir', type=Path, required=True)
    args = parser.parse_args()
    verify(args.source_root.resolve(), args.measurement_cache, args.report_dir)


if __name__ == '__main__':
    main()
