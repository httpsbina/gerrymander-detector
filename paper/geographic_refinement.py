"""Evaluate geometry measures at every saved frozen checkpoint."""

import argparse
import csv
from importlib import metadata
import json
import os
from pathlib import Path
import pickle
import re
import sys

import arviz as az
import geopandas as gpd
import numpy as np
import pandas as pd
from pyproj import Geod, Transformer
from scipy.spatial.distance import cdist
import shapely

from paper.geographic_clustering import CAMPAIGN, scores, sha
from paper.geographic_geometry import block_master
from paper.review_precision import check_freeze, finite_call, half_comparison, tail_diagnostics

METRICS = ('silhouette', 'normalized_rms_radius', 'mean_polsby_popper')


def moment_radius(population, sx, sy, q, labels):
    """Population-exact within-district dispersion for the recorded block centroids."""
    labels = np.asarray(labels, dtype=int)
    if (labels < 1).any() or not np.isfinite(np.column_stack([population, sx, sy, q])).all():
        raise ValueError('Invalid moments or labels')
    pop = np.bincount(labels, weights=population)[1:]
    x = np.bincount(labels, weights=sx)[1:]
    y = np.bincount(labels, weights=sy)[1:]
    squares = np.bincount(labels, weights=q)[1:]
    if (pop <= 0).any():
        raise ValueError('Missing or empty district')
    within = squares - (x ** 2 + y ** 2) / pop
    total = q.sum() - (sx.sum() ** 2 + sy.sum() ** 2) / population.sum()
    if (within < 0).any() or total <= 0:
        raise ValueError('Invalid squared-distance moments')
    return float(np.sqrt(within.sum() / total)), np.sqrt(within / pop)


def boundary_scores(area, perimeter, edges, labels):
    labels = np.asarray(labels, dtype=int)
    if (labels < 1).any():
        raise ValueError('Invalid district labels')
    district_area = np.bincount(labels, weights=area)[1:]
    district_perimeter = np.bincount(labels, weights=perimeter)[1:]
    left, right, length = edges
    same = labels[left] == labels[right]
    district_perimeter -= 2 * np.bincount(labels[left[same]], weights=length[same], minlength=len(district_perimeter) + 1)[1:]
    if (district_area <= 0).any() or (district_perimeter <= 0).any():
        raise ValueError('Invalid district area or perimeter')
    pp = 4 * np.pi * district_area / district_perimeter ** 2
    if not np.isfinite(pp).all() or (pp > 1 + 1e-10).any():
        raise ValueError('Invalid compactness')
    return pp, district_area, district_perimeter



def verify_boundary_union(geometries, area, perimeter, edges, labels):
    labels = np.asarray(labels, dtype=int)
    direct = [shapely.union_all(geometries[labels == number]) for number in range(1, int(max(labels)) + 1)]
    if shapely.is_empty(direct).any() or not shapely.is_valid(direct).all():
        raise ValueError('Empty or invalid direct district union')
    pp, district_area, district_perimeter = boundary_scores(area, perimeter, edges, labels)
    actual_area, actual_perimeter = shapely.area(direct), shapely.length(direct)
    if not np.allclose(district_area, actual_area, rtol=1e-10, atol=1e-4) or not np.allclose(district_perimeter, actual_perimeter, rtol=1e-10, atol=1e-4):
        raise ValueError('Shared-boundary formula and direct union differ')
    return {'maximum_area_relative_error': float(np.max(np.abs(district_area - actual_area) / actual_area)), 'maximum_perimeter_relative_error': float(np.max(np.abs(district_perimeter - actual_perimeter) / actual_perimeter))}


def trace_hashes(root, spec, seed):
    tag = f"{spec['epsilon']:g}".replace('.', 'p')
    found = {}
    paths = (root / spec['input_dir']).glob(f"{spec['prefix']}_chain_eps{tag}_seed{seed}_steps*.csv")
    for path in paths:
        match = re.search(r'_steps(\d+)-(\d+)\.csv$', path.name)
        if not match or int(match[1]) >= spec['steps']:
            continue
        with path.open() as stream:
            for row in csv.DictReader(stream):
                step = int(row['step'])
                if step >= spec['steps']:
                    continue
                if step in found:
                    raise ValueError('Overlapping trace states')
                found[step] = row['plan_hash']
    if set(found) != set(range(spec['steps'])):
        raise ValueError('Incomplete trace history')
    return found


def sample_points(master, coordinates, seed, size=2048):
    draws = np.random.default_rng(seed).choice(len(master), size, replace=True, p=master.TOTPOP.to_numpy() / master.TOTPOP.sum())
    return draws, coordinates[draws]


def geodesic_matrix(points):
    lon, lat = Transformer.from_crs(5070, 4269, always_xy=True).transform(points[:, 0], points[:, 1])
    n = len(points)
    first, second = np.triu_indices(n, 1)
    _, _, distance = Geod(ellps='GRS80').inv(lon[first], lat[first], lon[second], lat[second])
    matrix = np.zeros((n, n))
    matrix[first, second], matrix[second, first] = distance, distance
    return matrix


def run(root, cache, output):
    if output.exists():
        raise FileExistsError(output)
    output.mkdir(parents=True)
    records, rows, districts, replication, union_checks = {}, [], [], [], []
    inventory = json.loads((cache / 'inventory.json').read_text())
    for state, item in inventory['states'].items():
        for relative, expected in item['inputs'].items():
            if sha(root / relative) != expected:
                raise ValueError('Changed source for measurement cache')
        for name, expected in item['outputs'].items():
            if sha(cache / name) != expected:
                raise ValueError('Changed measurement cache')
    check_freeze(root, 'deliverables/nc-baseline-freeze-23000/freeze_manifest.json', records)
    check_freeze(root, 'deliverables/texas-baseline-freeze-70000/freeze_manifest.json', records)
    manifests = {'tx': CAMPAIGN / 'tx_shared45000_continuation_20261103/shared_070000/manifest.json', 'nc': CAMPAIGN / 'nc_primary_continuation/snapshot_003/manifest.json'}
    for state, manifest in manifests.items():
        master, _ = block_master(root, state)
        atoms = gpd.read_file(cache / f'{state}_atoms.gpkg', layer='atoms')
        points_file = np.load(cache / f'{state}_points.npz')
        if not np.array_equal(points_file['geoids'], master.GEOID20.to_numpy()):
            raise ValueError('Coordinate ordering differs')
        coordinates = points_file['coordinates']
        edge_file = np.load(cache / f'{state}_edges.npz')
        edges = edge_file['left'], edge_file['right'], edge_file['length']
        area, perimeter = atoms.geometry.area.to_numpy(), atoms.geometry.length.to_numpy()
        if int(atoms.population.sum()) != int(master.TOTPOP.sum()):
            raise ValueError('Population conservation failed')
        primary_index, primary_points = sample_points(master, coordinates, 20261109)
        primary_distance = cdist(primary_points, primary_points)
        samples = {}
        for seed in (20261109, 20261110, 20261111, 20261112):
            index, points = sample_points(master, coordinates, seed)
            samples[seed] = (index, points, cdist(points, points), geodesic_matrix(points))
        experiments = json.loads((root / manifest).read_text())['experiments']

        def evaluate(labels, group, seed, step, plan_hash=None, pilot=False):
            labels = np.asarray(labels, dtype=int)
            pp, district_area, district_perimeter = boundary_scores(area, perimeter, edges, labels)
            radius, district_radius = moment_radius(atoms.population.to_numpy(), atoms.sx.to_numpy(), atoms.sy.to_numpy(), atoms.q.to_numpy(), labels)
            atom_lookup = dict(zip(atoms.atom, labels))
            sample_labels = np.array([atom_lookup[value] for value in master.atom.iloc[primary_index]])
            silhouette = scores(primary_points, sample_labels, primary_distance)['silhouette']
            row = {'state': state, 'group': group, 'seed': seed, 'step': step, 'plan_hash': plan_hash, 'silhouette': silhouette, 'normalized_rms_radius': radius, 'mean_polsby_popper': float(pp.mean()), 'minimum_polsby_popper': float(pp.min())}
            rows.append(row)
            with (output / 'measurements.jsonl').open('a') as stream:
                stream.write(json.dumps(row, allow_nan=False) + '\n')
            if pilot:
                for number in range(1, len(pp) + 1):
                    districts.append({'state': state, 'group': group, 'seed': seed, 'step': step, 'district': number, 'polsby_popper': float(pp[number - 1]), 'area_m2': float(district_area[number - 1]), 'perimeter_m': float(district_perimeter[number - 1]), 'population_rms_radius_km': float(district_radius[number - 1] / 1000)})
                for sample_seed, (index, points, euclidean, geodesic) in samples.items():
                    sample_labels = np.array([atom_lookup[value] for value in master.atom.iloc[index]])
                    for n in (1024, 2048):
                        for distance_name, distance in [('EPSG5070', euclidean), ('geodesic', geodesic)]:
                            score = scores(points[:n], sample_labels[:n], distance[:n, :n])['silhouette']
                            replication.append({'state': state, 'group': group, 'seed': seed, 'step': step, 'sample_seed': sample_seed, 'sample_size': n, 'distance': distance_name, 'silhouette': score})
            return row

        def direct_union_check(labels, group, seed, step):
            checked = verify_boundary_union(atoms.geometry.to_numpy(), area, perimeter, edges, labels)
            union_checks.append({'state': state, 'group': group, 'seed': seed, 'step': step, **checked})

        for year in ([2025] if state == 'tx' else [2023, 2025]):
            labels = atoms[f'enacted_{year}'].to_numpy(dtype=int)
            evaluate(labels, f'enacted_{year}', None, None, pilot=True)
            direct_union_check(labels, f'enacted_{year}', None, None)
        print(state, 'enacted scores complete', flush=True)
        for group, spec in experiments.items():
            dataset = root / spec['dataset']
            if sha(dataset) != spec['dataset_sha256']:
                raise ValueError('Changed simulation dataset')
            units = gpd.read_file(dataset, layer='precincts', ignore_geometry=True).UNIQUE_ID
            if not units.is_unique or set(units) != set(master.unit):
                raise ValueError('Unit coverage differs')
            lookup = dict(zip(units, range(len(units))))
            nodes = np.array([lookup[unit] for unit in atoms.unit])
            directories = [root / CAMPAIGN / group / 'checkpoints', root / 'outputs/analysis/rebuild_campaign_2026-11-02' / group / 'checkpoints']
            if group == 'tx_dispersed':
                directories = [root / CAMPAIGN / 'texas_independent_dispersed/checkpoints']
            tag = f"{spec['epsilon']:g}".replace('.', 'p')
            pilot = set(np.round(np.linspace(1000, spec['steps'], 10) / 100).astype(int) * 100)
            for seed in spec['seeds']:
                trace = trace_hashes(root, spec, seed)
                lineage = None
                for boundary in range(100, spec['steps'] + 1, 100):
                    name = f"{spec['prefix']}_checkpoint_eps{tag}_seed{seed}_next{boundary}.pkl"
                    paths = [directory / name for directory in directories if (directory / name).is_file()]
                    hashes = {sha(path) for path in paths}
                    if not paths or len(hashes) != 1:
                        raise ValueError(f'Missing or conflicting checkpoint {name}')
                    path = paths[0]
                    records[str(path.relative_to(root))] = next(iter(hashes))
                    with path.open('rb') as stream:
                        checkpoint = pickle.load(stream)
                    provenance = checkpoint['provenance']
                    if lineage is None:
                        lineage = provenance
                    if provenance != lineage or provenance['dataset_sha256'] != spec['dataset_sha256']:
                        raise ValueError('Changed checkpoint provenance')
                    for key, filename in [('runner_sha256', 'src/chain/run_ensemble.py'), ('checkpoint_code_sha256', 'src/chain/checkpoint_integrity.py')]:
                        if provenance[key] != sha(root / filename):
                            raise ValueError('Changed checkpoint source')
                    config = provenance['configuration']
                    if config['epsilon'] != spec['epsilon'] or config['node_repeats'] != spec['node_repeats'] or config['sample_every'] != 1:
                        raise ValueError('Changed checkpoint configuration')
                    if checkpoint['version'] != 2 or checkpoint['seed'] != seed or checkpoint['next_step'] != boundary or checkpoint['plan_hash'] != trace[boundary - 1]:
                        raise ValueError('Checkpoint identity or trace differs')
                    if set(checkpoint['assignment']) != set(range(len(units))):
                        raise ValueError('Missing checkpoint units')
                    labels = np.array([checkpoint['assignment'][int(node)] for node in nodes])
                    evaluate(labels, group, seed, boundary - 1, checkpoint['plan_hash'], boundary in pilot)
                    if boundary == spec['steps']:
                        direct_union_check(labels, group, seed, boundary - 1)
                    if boundary % 10000 == 0:
                        print(state, group, seed, boundary, flush=True)
                print(state, group, seed, 'complete', flush=True)
                pd.DataFrame(rows).to_csv(output / 'progress_scores.csv', index=False)
        print(state, 'all measurements complete', flush=True)
    table = pd.DataFrame(rows)
    table.to_csv(output / 'scores.csv', index=False)
    pd.DataFrame(districts).to_csv(output / 'district_scores.csv', index=False)
    pd.DataFrame(replication).to_csv(output / 'silhouette_replications.csv', index=False)
    comparisons, diagnostics, warmups, halves = [], [], [], []
    for state, subset in table.groupby('state'):
        simulated = subset[~subset.group.str.startswith('enacted')]
        enacted = subset[subset.group.str.startswith('enacted')]
        for group in ['joint', *sorted(simulated.group.unique())]:
            values = simulated if group == 'joint' else simulated[simulated.group == group]
            retained = values[values.step >= 500]
            for metric in METRICS:
                arrays = [chain.sort_values('step')[metric].to_numpy() for _, chain in retained.groupby(['group', 'seed'])]
                samples_array = np.stack(arrays)
                diag = {'state': state, 'group': group, 'metric': metric, 'chains': len(arrays), 'checkpoints_per_chain': samples_array.shape[1], 'mean': float(samples_array.mean()), 'rhat': finite_call(lambda: az.rhat(samples_array, method='rank')), 'bulk_ess': finite_call(lambda: az.ess(samples_array, method='bulk')), 'tail_ess': finite_call(lambda: az.ess(samples_array, method='tail')), 'mcse_mean': finite_call(lambda: az.mcse(samples_array, method='mean'))}
                diagnostics.append(diag)
                halves.append({'state': state, 'group': group, 'metric': metric, **half_comparison(samples_array)})
                for warmup in (0, 250, 500, 1000):
                    array = np.stack([chain.sort_values('step')[metric].to_numpy() for _, chain in values[values.step >= warmup].groupby(['group', 'seed'])])
                    warmups.append({'state': state, 'group': group, 'metric': metric, 'warmup': warmup, 'checkpoints_per_chain': array.shape[1], 'mean': float(array.mean()), 'rhat': finite_call(lambda: az.rhat(array, method='rank')), 'bulk_ess': finite_call(lambda: az.ess(array, method='bulk')), 'tail_ess': finite_call(lambda: az.ess(array, method='tail'))})
                for plan in enacted.to_dict('records'):
                    x = retained[metric].to_numpy()
                    tail = tail_diagnostics(samples_array, plan[metric])
                    comparisons.append({'state': state, 'group': group, 'metric': metric, 'enacted': plan['group'], 'value': plan[metric], 'checkpoints': len(x), 'median': float(np.median(x)), 'minimum': float(x.min()), 'maximum': float(x.max()), 'tail': tail})
    result = {'method': 'Every available 100-state checkpoint; recorded state next_step minus one; main warmup 500. Block-centroid population moments and block-union boundary scores use all Census blocks. Silhouette uses a fixed population sample, with independent-sample and geodesic pilot comparisons.', 'process_nice': os.getpriority(os.PRIO_PROCESS, 0), 'primary_sample_seed': 20261109, 'silhouette_sample_size': 2048, 'checkpoint_measurements': len(table[~table.group.str.startswith('enacted')]), 'retained_checkpoint_measurements': len(table[(~table.group.str.startswith('enacted')) & (table.step >= 500)]), 'research_ready': False, 'freeze_changed': False, 'comparisons': comparisons, 'diagnostics': diagnostics, 'warmups': warmups, 'halves': halves, 'direct_union_checks': union_checks, 'measurement_inventory': inventory, 'input_checksums': records, 'code_checksums': {name: sha(Path(__file__).resolve().parents[1] / name) for name in ['paper/geographic_refinement.py', 'paper/geographic_geometry.py', 'paper/geographic_analysis_plan.md']}, 'python': sys.version, 'packages': {name: metadata.version(name) for name in ['arviz', 'numpy', 'scipy', 'pandas', 'geopandas', 'shapely', 'pyproj']}}
    (output / 'results.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    print(output, 'complete', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--measurement-cache', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    run(args.source_root.resolve(), args.measurement_cache, args.output_dir)


if __name__ == '__main__':
    main()
