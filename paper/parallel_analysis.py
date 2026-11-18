"""Pair frozen electoral outcomes with geographic distance and variation measures."""

import argparse
import csv
from importlib import metadata
import json
import os
from pathlib import Path
import pickle
import platform
import sys

import arviz as az
import geopandas as gpd
import numpy as np
import pandas as pd

from paper.geographic_clustering import CAMPAIGN, sha
from paper.geographic_geometry import block_master
from paper.review_precision import finite_call, half_comparison

DISTANCE_METRICS = ('mean_distance_km', 'sd_distance_km', 'distance_cv', 'inverse_distance_cv', 'mean_district_cv')
GEOGRAPHIC_METRICS = ('silhouette', 'normalized_rms_radius', 'mean_polsby_popper', *DISTANCE_METRICS)


def radial_statistics(points, population, labels):
    """Population-weighted radial moments, including zero-weight locations."""
    points, population, labels = np.asarray(points, dtype=float), np.asarray(population, dtype=float), np.asarray(labels, dtype=int)
    if points.shape != (len(population), 2) or len(labels) != len(population) or not np.isfinite(points).all() or not np.isfinite(population).all() or (population < 0).any() or population.sum() <= 0 or (labels < 1).any():
        raise ValueError('Invalid population locations or labels')
    mass = np.bincount(labels, weights=population)
    if (mass[1:] <= 0).any():
        raise ValueError('Missing or empty district')
    centers = np.column_stack([np.divide(np.bincount(labels, weights=population * points[:, axis]), mass, out=np.zeros_like(mass), where=mass > 0) for axis in (0, 1)])
    distances = np.linalg.norm(points - centers[labels], axis=1)
    mean = np.bincount(labels, weights=population * distances) / np.where(mass > 0, mass, 1)
    variance = np.bincount(labels, weights=population * (distances - mean[labels]) ** 2) / np.where(mass > 0, mass, 1)
    sd = np.sqrt(variance)
    mean_all = float(np.average(distances, weights=population))
    sd_all = float(np.sqrt(np.average((distances - mean_all) ** 2, weights=population)))
    rms_all = float(np.sqrt(np.average(distances ** 2, weights=population)))
    if not np.isclose(rms_all ** 2, mean_all ** 2 + sd_all ** 2, rtol=1e-12, atol=1e-8):
        raise ValueError('Radial mean/variance identity failed')
    districts = []
    for number in range(1, len(mass)):
        districts.append({'district': number, 'population': float(mass[number]), 'mean_distance_km': float(mean[number] / 1000), 'sd_distance_km': float(sd[number] / 1000), 'distance_cv': float(sd[number] / mean[number]) if mean[number] > 0 else None, 'inverse_distance_cv': float(mean[number] / sd[number]) if sd[number] > 0 else None})
    district_cv = [item['distance_cv'] for item in districts]
    mean_district_cv = float(np.average(district_cv, weights=mass[1:])) if all(item is not None for item in district_cv) else None
    return {'mean_distance_km': mean_all / 1000, 'sd_distance_km': sd_all / 1000, 'rms_distance_km': rms_all / 1000, 'distance_cv': sd_all / mean_all if mean_all > 0 else None, 'inverse_distance_cv': mean_all / sd_all if sd_all > 0 else None, 'mean_district_cv': mean_district_cv}, districts


def trace_checkpoint_rows(root, spec, seed, registered, records):
    tag = f"{spec['epsilon']:g}".replace('.', 'p')
    seen = np.zeros(spec['steps'], dtype=bool)
    retained_counts, checkpoints = {}, {}
    total, retained = 0, 0
    for path in sorted((root / spec['input_dir']).glob(f"{spec['prefix']}_chain_eps{tag}_seed{seed}_steps*.csv")):
        actual = sha(path)
        relative = str(path.relative_to(root))
        if relative in records and records[relative] != actual:
            raise ValueError('Changed chain segment')
        records[relative] = actual
        with path.open() as stream:
            for row in csv.DictReader(stream):
                step = int(row['step'])
                if step >= spec['steps']:
                    continue
                if step < 0 or seen[step]:
                    raise ValueError('Overlapping or invalid trace step')
                seen[step] = True
                seats = float(row['dem_seats'])
                if not np.isfinite(seats) or seats != int(seats):
                    raise ValueError('Invalid stored seat score')
                seats = int(seats)
                if step >= spec['warmup']:
                    total += seats
                    retained += 1
                    retained_counts[seats] = retained_counts.get(seats, 0) + 1
                if step % 100 == 99:
                    checkpoints[step] = {'plan_hash': row['plan_hash'], 'dem_seats': seats}
    if not seen.all() or retained != registered['retained_states'] or not np.isclose(total / retained, registered['dem_seats_mean'], rtol=1e-12, atol=1e-12):
        raise ValueError('Trace coverage or frozen mean differs')
    return checkpoints, {'seed': seed, 'recorded_states': spec['steps'], 'warmup': spec['warmup'], 'retained_states': retained, 'seat_sum': total, 'mean_democratic_seats': total / retained, 'seat_counts': retained_counts}


def association(x, y):
    x, y = np.asarray(x), np.asarray(y)
    if len(x) < 3 or not np.isfinite(x).all() or not np.isfinite(y).all():
        return {'spearman': None, 'status': 'unavailable_invalid_or_short_series', 'observations': len(x)}
    if len(np.unique(x)) < 2 or len(np.unique(y)) < 2:
        return {'spearman': None, 'status': 'unavailable_constant_series', 'observations': len(x)}
    value = float(pd.Series(x).corr(pd.Series(y), method='spearman'))
    return {'spearman': value, 'status': 'finite' if np.isfinite(value) else 'nonfinite', 'observations': len(x)}


def run(root, cache, geographic_review, election_review, output):
    if output.exists():
        raise FileExistsError(output)
    output.mkdir(parents=True)
    prior = json.loads((geographic_review / 'results.json').read_text())
    geo = pd.read_csv(geographic_review / 'scores.csv')
    election = json.loads((election_review / 'results.json').read_text())
    certificate = json.loads((election_review / 'assignment_validation.json').read_text())
    if sha(election_review / 'results.json') != certificate['results_sha256']:
        raise ValueError('Election validation receipt differs')
    records = dict(prior['input_checksums'])
    for relative, expected in election['input_checksums'].items():
        if relative in records and records[relative] != expected:
            raise ValueError('Conflicting geographic and election provenance')
        records[relative] = expected
    for relative, expected in records.items():
        if sha(root / relative) != expected:
            raise ValueError(f'Changed research input: {relative}')
    registered = json.loads(Path('paper/results.json').read_text())
    rows, district_rows, full_histories = [], [], []
    enacted_seats = {}
    for state in ('tx', 'nc'):
        master, _ = block_master(root, state)
        for name, expected in prior['measurement_inventory']['states'][state]['outputs'].items():
            if sha(cache / name) != expected:
                raise ValueError('Changed geographic cache')
        atoms = gpd.read_file(cache / f'{state}_atoms.gpkg', layer='atoms', ignore_geometry=True)
        point_file = np.load(cache / f'{state}_points.npz')
        if not np.array_equal(point_file['geoids'], master.GEOID20.to_numpy()):
            raise ValueError('Block identity differs')
        points = point_file['coordinates'] - point_file['origin']
        population = master.TOTPOP.to_numpy(dtype=float)
        center = np.average(points, weights=population, axis=0)
        statewide_rms = float(np.sqrt(np.average(np.sum((points - center) ** 2, axis=1), weights=population)))
        atom_lookup = dict(zip(atoms.atom, range(len(atoms))))
        block_atoms = np.array([atom_lookup[value] for value in master.atom])
        manifest = 'tx_shared45000_continuation_20261103/shared_070000/manifest.json' if state == 'tx' else 'nc_primary_continuation/snapshot_003/manifest.json'
        specs = json.loads((root / CAMPAIGN / manifest).read_text())['experiments']
        models = election['results'][state]['models']
        president = [model['office'] for model in models].index('President')
        enacted_seats[state] = {year: values[president] for year, values in election['results'][state]['enacted_seats'].items()}
        state_geo = geo[geo.state == state]

        def evaluate(base, atom_labels, seats, pilot=False):
            labels = np.asarray(atom_labels, dtype=int)[block_atoms]
            stats, districts = radial_statistics(points, population, labels)
            if not np.isclose(stats['rms_distance_km'] * 1000 / statewide_rms, base['normalized_rms_radius'], rtol=1e-11, atol=1e-12):
                raise ValueError('Direct radial RMS differs from registered geographic score')
            if any(stats[key] is None or not np.isfinite(stats[key]) for key in DISTANCE_METRICS):
                raise ValueError('Undefined geographic variation measure on real data')
            if not np.isclose(stats['distance_cv'] * stats['inverse_distance_cv'], 1, rtol=1e-12):
                raise ValueError('CV reciprocal identity failed')
            row = {key: base[key] for key in ['state', 'group', 'seed', 'step', 'plan_hash', 'silhouette', 'normalized_rms_radius', 'mean_polsby_popper']}
            row.update({'democratic_seats_2024_presidential_model': seats, **stats})
            rows.append(row)
            if pilot:
                district_rows.extend({key: row[key] for key in ['state', 'group', 'seed', 'step']} | district for district in districts)
            with (output / 'measurements.jsonl').open('a') as stream:
                stream.write(json.dumps({key: (None if isinstance(value, float) and np.isnan(value) else value) for key, value in row.items()}, allow_nan=False) + '\n')

        for base in state_geo[state_geo.group.str.startswith('enacted')].to_dict('records'):
            year = base['group'].split('_')[-1]
            evaluate(base, atoms[f'enacted_{year}'].to_numpy(), enacted_seats[state][year], True)
        for group, spec in specs.items():
            frame = gpd.read_file(root / spec['dataset'], layer='precincts', ignore_geometry=True)
            if not frame.UNIQUE_ID.is_unique or set(frame.UNIQUE_ID) != set(master.unit):
                raise ValueError('Simulation unit identity differs')
            unit_lookup = dict(zip(frame.UNIQUE_ID, range(len(frame))))
            nodes = np.array([unit_lookup[unit] for unit in atoms.unit])
            tag = f"{spec['epsilon']:g}".replace('.', 'p')
            pilot = set(np.round(np.linspace(1000, spec['steps'], 10) / 100).astype(int) * 100)
            directories = [root / CAMPAIGN / group / 'checkpoints', root / 'outputs/analysis/rebuild_campaign_2026-11-02' / group / 'checkpoints']
            if group == 'tx_dispersed':
                directories = [root / CAMPAIGN / 'texas_independent_dispersed/checkpoints']
            for seed in spec['seeds']:
                frozen = next(item for item in registered['texas' if state == 'tx' else 'nc']['chain_summary'] if item['experiment'] == group and item['seed'] == seed)
                trace, full = trace_checkpoint_rows(root, spec, seed, frozen, records)
                full_histories.append({'state': state, 'group': group, **full})
                selected = state_geo[(state_geo.group == group) & (state_geo.seed == seed)].sort_values('step')
                for base in selected.to_dict('records'):
                    step, boundary = int(base['step']), int(base['step']) + 1
                    stored = trace[step]
                    if stored['plan_hash'] != base['plan_hash']:
                        raise ValueError('Geographic/electoral plan identity differs')
                    name = f"{spec['prefix']}_checkpoint_eps{tag}_seed{seed}_next{boundary}.pkl"
                    paths = [directory / name for directory in directories if (directory / name).is_file()]
                    hashes = {sha(path) for path in paths}
                    expected = {records[str(path.relative_to(root))] for path in paths if str(path.relative_to(root)) in records}
                    if not paths or len(hashes) != 1 or hashes != expected:
                        raise ValueError('Missing or changed checkpoint')
                    with paths[0].open('rb') as stream:
                        checkpoint = pickle.load(stream)
                    if checkpoint['seed'] != seed or checkpoint['next_step'] != boundary or checkpoint['plan_hash'] != base['plan_hash']:
                        raise ValueError('Checkpoint identity differs')
                    if set(checkpoint['assignment']) != set(range(len(frame))):
                        raise ValueError('Missing checkpoint units')
                    labels = [checkpoint['assignment'][int(node)] for node in nodes]
                    evaluate(base, labels, stored['dem_seats'], boundary in pilot)
                print(state, group, seed, 'complete', flush=True)
    table = pd.DataFrame(rows)
    table.to_csv(output / 'paired_presidential.csv', index=False)
    pd.DataFrame(district_rows).to_csv(output / 'district_distances.csv', index=False)
    local_elections = pd.DataFrame(json.loads((election_review / 'checkpoint_scores.json').read_text()))
    keys = ['state', 'group', 'seed', 'step', 'plan_hash']
    if local_elections.duplicated(keys).any() or table[~table.group.str.startswith('enacted')].duplicated(keys).any():
        raise ValueError('Duplicate paired map identity')
    paired = local_elections.merge(table, on=keys, how='left', validate='one_to_one', indicator=True)
    if len(paired) != certificate['checkpoints_verified'] or not (paired._merge == 'both').all() or not np.array_equal(paired.President, paired.democratic_seats_2024_presidential_model):
        raise ValueError('Existing election scores do not match the geographic maps')
    paired.drop(columns='_merge').to_csv(output / 'paired_existing_elections.csv', index=False)
    comparisons, diagnostics, warmups, halves, correlations = [], [], [], [], []
    for state, subset in table.groupby('state'):
        simulated = subset[(~subset.group.str.startswith('enacted')) & (subset.step >= 500)]
        for cohort in ['joint', *sorted(simulated.group.unique())]:
            selected = simulated if cohort == 'joint' else simulated[simulated.group == cohort]
            for metric in DISTANCE_METRICS:
                arrays = np.stack([chain.sort_values('step')[metric].to_numpy() for _, chain in selected.groupby(['group', 'seed'])])
                diagnostics.append({'state': state, 'cohort': cohort, 'metric': metric, 'chains': arrays.shape[0], 'checkpoints_per_chain': arrays.shape[1], 'mean': float(arrays.mean()), 'rhat': finite_call(lambda: az.rhat(arrays, method='rank')), 'bulk_ess': finite_call(lambda: az.ess(arrays, method='bulk')), 'tail_ess': finite_call(lambda: az.ess(arrays, method='tail')), 'mcse_mean': finite_call(lambda: az.mcse(arrays, method='mean'))})
                halves.append({'state': state, 'cohort': cohort, 'metric': metric, **half_comparison(arrays)})
                for plan in subset[subset.group.str.startswith('enacted')].to_dict('records'):
                    x = selected[metric].to_numpy()
                    comparisons.append({'state': state, 'cohort': cohort, 'enacted': plan['group'], 'metric': metric, 'value': plan[metric], 'median': float(np.median(x)), 'q05': float(np.quantile(x, .05)), 'q95': float(np.quantile(x, .95)), 'at_or_below': int(np.sum(x <= plan[metric])), 'at_or_above': int(np.sum(x >= plan[metric])), 'checkpoints': len(x)})
            for metric in GEOGRAPHIC_METRICS:
                for scope, chunk in [('pooled', selected), *[(f'seed_{int(seed)}', chain) for (_, seed), chain in selected.groupby(['group', 'seed'])]]:
                    correlations.append({'state': state, 'cohort': cohort, 'election': 'President', 'sample': 'all_frozen_checkpoints', 'metric': metric, 'scope': scope, **association(chunk[metric], chunk.democratic_seats_2024_presidential_model)})
            all_chain_values = subset[(~subset.group.str.startswith('enacted')) & ((subset.group == cohort) if cohort != 'joint' else True)]
            for warmup in (0, 250, 500, 1000):
                for metric in DISTANCE_METRICS:
                    array = np.stack([chain.sort_values('step')[metric].to_numpy() for _, chain in all_chain_values[all_chain_values.step >= warmup].groupby(['group', 'seed'])])
                    warmups.append({'state': state, 'cohort': cohort, 'metric': metric, 'warmup': warmup, 'mean': float(array.mean()), 'rhat': finite_call(lambda: az.rhat(array, method='rank')), 'bulk_ess': finite_call(lambda: az.ess(array, method='bulk')), 'tail_ess': finite_call(lambda: az.ess(array, method='tail'))})
        offices = [model['office'] for model in election['results'][state]['models']]
        part = paired[paired.state == state]
        for cohort in ['joint', *sorted(part.group.unique())]:
            selected = part if cohort == 'joint' else part[part.group == cohort]
            for office in offices:
                for metric in GEOGRAPHIC_METRICS:
                    correlations.append({'state': state, 'cohort': cohort, 'election': office, 'sample': 'existing_election_checkpoint_subset', 'metric': metric, 'scope': 'pooled', **association(selected[metric], selected[office])})
    pd.DataFrame(correlations).to_csv(output / 'associations.csv', index=False)
    result = {'research_ready': False, 'freeze_changed': False, 'method': 'Same-map pairing by state, cohort, seed, recorded step and plan hash. Every available 100-state checkpoint is retained, with primary warmup 500. Distances use all 2020 Census block population and centroids; SD is the population-weighted population SD. CV is SD/mean, inverse CV is mean/SD. Their reciprocal relationship is not independent evidence. Correlations are descriptive Spearman coefficients without IID p-values.', 'election_model': '2024 observed election returns allocated to Census blocks by the existing RDH model; not actual 2026 congressional results.', 'checkpoint_interval': 100, 'full_frozen_histories': full_histories, 'enacted_presidential_seats': enacted_seats, 'comparisons': comparisons, 'diagnostics': diagnostics, 'warmups': warmups, 'halves': halves, 'input_checksums': records, 'linked_inputs': {str(path): sha(path) for path in [geographic_review / 'results.json', geographic_review / 'scores.csv', election_review / 'results.json', election_review / 'checkpoint_scores.json', election_review / 'assignment_validation.json', Path('paper/results.json')]}, 'existing_election_checkpoints_matched': len(paired), 'code_sha256': sha(__file__), 'process_nice': os.getpriority(os.PRIO_PROCESS, 0), 'runtime': {'python': sys.version, 'platform': platform.platform(), 'packages': {name: metadata.version(name) for name in ['numpy', 'scipy', 'pandas', 'geopandas', 'arviz']}}}
    (output / 'results.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    print(output, 'complete', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--measurement-cache', type=Path, required=True)
    parser.add_argument('--geographic-review', type=Path, required=True)
    parser.add_argument('--election-review', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    run(args.source_root.resolve(), args.measurement_cache, args.geographic_review, args.election_review, args.output_dir)


if __name__ == '__main__':
    main()
