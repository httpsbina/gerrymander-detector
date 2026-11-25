"""Separate enacted splits within simulation units from other measured boundaries."""

import argparse
import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

from paper.geographic_clustering import sha


def run(directory, cache):
    target = directory / 'partition_sensitivity.json'
    if target.exists():
        raise FileExistsError(target)
    result = json.loads((directory / 'results.json').read_text())
    table = pd.read_csv(directory / 'scores.csv')
    records = []
    for state in ('tx', 'nc'):
        atoms = gpd.read_file(cache / f'{state}_atoms.gpkg', layer='atoms', ignore_geometry=True)
        edges = np.load(cache / f'{state}_edges.npz')
        left, right, length = edges['left'], edges['right'], edges['length']
        same_unit = atoms.unit.to_numpy()[left] == atoms.unit.to_numpy()[right]
        neutral = table[(table.state == state) & (~table.group.str.startswith('enacted')) & (table.step >= 500)]
        native_difference = neutral.common_cut_edges - neutral.sampler_cut_edges
        for row in table[(table.state == state) & table.group.str.startswith('enacted')].to_dict('records'):
            year = row['group'].split('_')[-1]
            labels = atoms[f'enacted_{year}'].to_numpy()
            cut = labels[left] != labels[right]
            within = int((cut & same_unit).sum())
            between = int((cut & ~same_unit).sum())
            if within + between != int(row['common_cut_edges']):
                raise ValueError('Boundary partition does not recover measured cuts')
            values = neutral.common_cut_edges.to_numpy()
            records.append({'state': state, 'enacted': row['group'], 'all_cut_adjacencies': int(cut.sum()), 'within_simulation_unit_cuts': within, 'between_simulation_unit_cuts': between, 'within_unit_boundary_km': float(length[cut & same_unit].sum() / 1000), 'between_unit_boundary_km': float(length[cut & ~same_unit].sum() / 1000), 'neutral_between_unit_median': float(np.median(values)), 'neutral_between_unit_at_or_below_enacted': int(np.sum(values <= between)), 'neutral_between_unit_at_or_above_enacted': int(np.sum(values >= between)), 'neutral_checkpoints': len(values), 'neutral_within_unit_cuts': 0, 'neutral_common_minus_sampler_count_minimum': float(native_difference.min()), 'neutral_common_minus_sampler_count_maximum': float(native_difference.max()), 'neutral_common_minus_sampler_count_median': float(native_difference.median())})
    output = {'definition': 'All simulated assignments allocate entire simulation units, so their within-unit cut count is zero by construction. The between-unit statistic still counts atomic adjacencies and is not the original sampler cut-edge count. No assignment or measurement geometry is changed.', 'enacted_plans': records, 'source_results_sha256': sha(directory / 'results.json'), 'source_scores_sha256': sha(directory / 'scores.csv'), 'research_ready': False}
    target.write_text(json.dumps(output, indent=2, allow_nan=False) + '\n')
    pd.DataFrame(records).to_csv(directory / 'partition_sensitivity.csv', index=False)
    print(json.dumps(output, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--review-dir', type=Path, required=True)
    parser.add_argument('--measurement-cache', type=Path, required=True)
    args = parser.parse_args()
    run(args.review_dir, args.measurement_cache)


if __name__ == '__main__':
    main()
