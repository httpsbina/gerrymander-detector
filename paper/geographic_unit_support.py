"""Measure enacted splits without assigning split units to a single district."""

import argparse
import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

from paper.geographic_clustering import sha
from paper.geographic_geometry import block_master


def split_support(frame, unit='unit', district='district', population='population'):
    """Minimum population relabeling is a bound, not a constructed legal plan."""
    grouped = frame.groupby([unit, district], dropna=False).agg(population=(population, 'sum'), blocks=(population, 'size'))
    rows = []
    for key, part in grouped.groupby(level=0):
        rows.append({'unit': key, 'districts': len(part), 'population': int(part.population.sum()),
                     'minimum_population_relabeling': int(part.population.sum() - part.population.max()),
                     'minimum_block_relabeling': int(part.blocks.sum() - part.blocks.max())})
    return pd.DataFrame(rows)


def run(root, cache, directory):
    target = directory / 'unit_support.json'
    if target.exists():
        raise FileExistsError(target)
    records, plans, unit_rows = {}, [], []
    scores = pd.read_csv(directory / 'scores.csv')
    previous = json.loads(Path('paper/reviews/compactness-mechanisms-20261109/partition_sensitivity.json').read_text())
    for state in ('nc', 'tx'):
        master, master_path = block_master(root, state)
        records[str(master_path.relative_to(root))] = sha(master_path)
        atoms = gpd.read_file(cache / f'{state}_atoms.gpkg', layer='atoms', ignore_geometry=True)
        edges = np.load(cache / f'{state}_edges.npz')
        left, right, length = edges['left'], edges['right'], edges['length']
        units = pd.Categorical(atoms.unit).codes
        within = units[left] == units[right]
        pairs = np.sort(np.column_stack([units[left], units[right]]), axis=1)
        for year in (['2023', '2025'] if state == 'nc' else ['2025']):
            support = split_support(master.rename(columns={f'DISTRICT_{year}': 'district', 'TOTPOP': 'population'}))
            split = support[support.districts > 1]
            unit_rows.extend({'state': state, 'enacted': year, **row} for row in split.to_dict('records'))
            labels = atoms['enacted_' + year].to_numpy()
            cut = labels[left] != labels[right]
            between_cut = cut & ~within
            cut_pairs = set(map(tuple, pairs[between_cut]))
            uncut_pairs = set(map(tuple, pairs[(~cut) & ~within]))
            reference = scores[scores.state == state]
            old = next(r for r in previous['enacted_plans'] if r['state'] == state and r['enacted'] == 'enacted_' + year)
            if int((cut & within).sum()) != old['within_simulation_unit_cuts'] or int(between_cut.sum()) != old['between_simulation_unit_cuts']:
                raise ValueError('Previous boundary partition differs')
            plans.append({'state': state, 'enacted': year, 'simulation_units': len(support), 'split_units': len(split),
                          'zero_population_split_units': int((split.population == 0).sum()),
                          'state_population': int(master.TOTPOP.sum()), 'population_in_split_units': int(split.population.sum()),
                          'minimum_population_relabeling_for_whole_units': int(split.minimum_population_relabeling.sum()),
                          'minimum_block_relabeling_for_whole_units': int(split.minimum_block_relabeling.sum()),
                          'within_unit_cut_atomic_edges': int((cut & within).sum()),
                          'between_unit_cut_atomic_edges': int(between_cut.sum()),
                          'distinct_between_unit_pairs_with_any_cut': len(cut_pairs),
                          'between_unit_pairs_with_both_cut_and_uncut_contacts': len(cut_pairs & uncut_pairs),
                          'within_unit_boundary_km': float(length[cut & within].sum() / 1000),
                          'total_internal_boundary_km': float(length[cut].sum() / 1000),
                          'reference_native_cut_median': float(reference.sampler_cut_edges.median()),
                          'reference_distinct_pair_count_at_or_above_any_cut_statistic': int((reference.sampler_cut_edges >= len(cut_pairs)).sum()),
                          'reference_checkpoints': len(reference),
                          'native_enacted_cut_score_status': 'unavailable_split_unit_assignment' if len(split) else 'representable'})
    pd.DataFrame(unit_rows).to_csv(directory / 'enacted_split_units.csv', index=False)
    output = {'plans': plans, 'method': 'Every enacted block assignment is retained. Minimum relabeling counts are separate combinatorial lower bounds, not an altered map or a contiguity/balance-feasible plan. Any-cut unit-pair counts use observed cross-district atomic contacts; a split-unit map can have cut and uncut contacts on the same pair, unlike a whole-unit sampled map.',
              'input_hashes': records, 'source_scores_sha256': sha(directory / 'scores.csv'),
              'previous_partition_sha256': sha('paper/reviews/compactness-mechanisms-20261109/partition_sensitivity.json'),
              'code_sha256': sha(__file__), 'research_ready': False}
    target.write_text(json.dumps(output, indent=2, allow_nan=False) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['source-root', 'measurement-cache', 'review-dir']:
        parser.add_argument('--' + name, type=Path, required=True)
    a = parser.parse_args()
    run(a.source_root.resolve(), a.measurement_cache, a.review_dir)
