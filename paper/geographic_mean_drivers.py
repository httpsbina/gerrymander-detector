"""Decompose each chain's largest window shift in mean distance by county."""

import argparse
import json
from pathlib import Path
import pickle

import geopandas as gpd
import numpy as np
import pandas as pd

from paper.frozen_elections import MANIFESTS
from paper.geographic_clustering import sha
from paper.geographic_geometry import block_master


def run(root, cache, prior, directory):
    target = directory / 'mean_distance_county_drivers.csv'
    if target.exists():
        raise FileExistsError(target)
    windows = pd.read_csv(directory / 'chain_windows.csv')
    scores = pd.read_csv(directory / 'scores.csv')
    recorded = json.loads((prior / 'results.json').read_text())['input_checksums']
    checkpoint_paths = {}
    for relative in recorded:
        if relative.endswith('.pkl'):
            checkpoint_paths.setdefault(Path(relative).name, []).append(root / relative)
    selections, rows, checked = [], [], 0
    for state in ('nc', 'tx'):
        master, _ = block_master(root, state)
        atoms = gpd.read_file(cache / f'{state}_atoms.gpkg', layer='atoms', ignore_geometry=True)
        points = np.load(cache / f'{state}_points.npz')
        if not np.array_equal(master.GEOID20.to_numpy(), points['geoids']):
            raise ValueError('Block order differs')
        coordinates = points['coordinates'] - points['origin']
        population = master.TOTPOP.to_numpy(dtype=float)
        atom_lookup = dict(zip(atoms.atom, range(len(atoms))))
        block_atoms = np.array([atom_lookup[key] for key in master.atom])
        county_ids, county_index = np.unique(master.GEOID20.str[:5].to_numpy(), return_inverse=True)
        county_population = np.bincount(county_index, weights=population)
        names = pd.read_csv('paper/reviews/compactness-mechanisms-20261109/county_half_shifts.csv', dtype={'county_fips': str})
        names = names[names.state == state].drop_duplicates('county_fips').set_index('county_fips').county.to_dict()
        specs = json.loads((root / MANIFESTS[state]).read_text())['experiments']
        for group, spec in specs.items():
            frame = gpd.read_file(root / spec['dataset'], layer='precincts', ignore_geometry=True)
            lookup = dict(zip(frame.UNIQUE_ID, range(len(frame))))
            atom_nodes = np.array([lookup[u] for u in atoms.unit])
            for seed in spec['seeds']:
                chain_windows = windows[(windows.state == state) & (windows.group == group) & (windows.seed == seed)].sort_values('window_start').reset_index(drop=True)
                change = chain_windows.mean_distance_km.diff()
                index = int(change.abs().idxmax())
                pair = chain_windows.iloc[[index - 1, index]]
                contributions = []
                for window in pair.itertuples():
                    selected = scores[(scores.state == state) & (scores.group == group) & (scores.seed == seed) & (scores.step >= window.window_start) & (scores.step < window.window_end_exclusive)]
                    values = []
                    for base in selected.itertuples():
                        tag = f"{spec['epsilon']:g}".replace('.', 'p')
                        name = f"{spec['prefix']}_checkpoint_eps{tag}_seed{seed}_next{int(base.step) + 1}.pkl"
                        candidates = checkpoint_paths[name]
                        if any(sha(p) != recorded[str(p.relative_to(root))] for p in candidates):
                            raise ValueError('Changed checkpoint')
                        with candidates[0].open('rb') as stream:
                            checkpoint = pickle.load(stream)
                        if checkpoint['plan_hash'] != base.plan_hash:
                            raise ValueError('Plan identity differs')
                        labels = np.array([checkpoint['assignment'][int(node)] for node in atom_nodes], dtype=int)
                        mass = np.bincount(labels, weights=atoms.population)
                        cx = np.bincount(labels, weights=atoms.sx) / np.where(mass > 0, mass, 1)
                        cy = np.bincount(labels, weights=atoms.sy) / np.where(mass > 0, mass, 1)
                        block_labels = labels[block_atoms]
                        distances = np.hypot(coordinates[:, 0] - cx[block_labels], coordinates[:, 1] - cy[block_labels]) / 1000
                        contribution = np.bincount(county_index, weights=population * distances) / population.sum()
                        if not np.isclose(contribution.sum(), base.mean_distance_km, rtol=1e-12, atol=1e-10):
                            raise ValueError('County mean-distance identity failed')
                        values.append(contribution)
                        checked += 1
                    contributions.append(np.mean(values, axis=0))
                first, second = contributions
                if not np.isclose((second - first).sum(), change.iloc[index], rtol=1e-10, atol=1e-10):
                    raise ValueError('County window change does not recover global shift')
                a, b = pair.iloc[0], pair.iloc[1]
                selection = {'state': state, 'group': group, 'seed': seed, 'selection': 'largest_absolute_adjacent_window_mean_shift_for_this_chain',
                             'from_start': int(a.window_start), 'from_end_exclusive': int(a.window_end_exclusive),
                             'to_start': int(b.window_start), 'to_end_exclusive': int(b.window_end_exclusive),
                             'from_checkpoints': int(a.checkpoints), 'to_checkpoints': int(b.checkpoints),
                             'from_mean_km': a.mean_distance_km, 'to_mean_km': b.mean_distance_km,
                             'global_shift_km': float(change.iloc[index])}
                selections.append(selection)
                for i, county in enumerate(county_ids):
                    rows.append({**selection, 'county_fips': county, 'county': names[county],
                                 'county_population': int(county_population[i]), 'statewide_mean_contribution_before_km': first[i],
                                 'statewide_mean_contribution_after_km': second[i], 'statewide_mean_shift_contribution_km': second[i] - first[i],
                                 'county_resident_mean_before_km': first[i] * population.sum() / county_population[i],
                                 'county_resident_mean_after_km': second[i] * population.sum() / county_population[i]})
                print(state, group, seed, 'county means complete', flush=True)
    pd.DataFrame(rows).to_csv(target, index=False)
    receipt = {'selection': 'One largest absolute adjacent-window shift from every chain; exploratory attribution, not a convergence pass or a selected ensemble. NC final windows have 3000 states, with window lengths and checkpoint counts recorded.',
               'assignments_recomputed': checked, 'window_pairs': selections, 'checks': ['all selected checkpoint hashes and identities', 'all county contributions sum to original block mean', 'all window differences sum to original global shift'],
               'source_scores_sha256': sha(directory / 'scores.csv'), 'source_windows_sha256': sha(directory / 'chain_windows.csv'),
               'code_sha256': sha(__file__), 'research_ready': False}
    (directory / 'mean_distance_county_verification.json').write_text(json.dumps(receipt, indent=2, allow_nan=False) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['source-root', 'measurement-cache', 'parallel-review', 'review-dir']:
        parser.add_argument('--' + name, type=Path, required=True)
    a = parser.parse_args()
    run(a.source_root.resolve(), a.measurement_cache, a.parallel_review, a.review_dir)
