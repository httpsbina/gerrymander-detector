"""Attribute geographic mixing and unit-resolution effects without changing plans."""

import argparse
from importlib import metadata
import json
import os
from pathlib import Path
import pickle
import platform
import sys
import warnings

import arviz as az
import geopandas as gpd
from gerrychain import Graph
import numpy as np
import pandas as pd

from paper.compactness_mechanisms import county_contributions, load_county_moments
from paper.frozen_elections import MANIFESTS
from paper.geographic_clustering import CAMPAIGN, sha
from paper.geographic_geometry import block_master
from paper.parallel_analysis import GEOGRAPHIC_METRICS
from paper.review_precision import finite_call
from paper.validate_checkpoint_elections import assignment_hash


def edge_partition(atom_pairs, atom_units, native_pairs):
    """Keep multiplicity separate from differences in the simple unit graphs."""
    atom_units = np.asarray(atom_units)
    within, pairs, multiplicity = 0, {}, {}
    for a, b in atom_pairs:
        u, v = int(atom_units[a]), int(atom_units[b])
        if u == v:
            within += 1
            continue
        key = tuple(sorted((u, v)))
        pairs[key] = True
        multiplicity[key] = multiplicity.get(key, 0) + 1
    common = set(pairs)
    native = {tuple(sorted(map(int, pair))) for pair in native_pairs}
    return common, multiplicity, common - native, native - common, within


def centroid_radial(population, sx, sy, q, labels):
    """Collapse locations to group centers while retaining exact second moments."""
    population, sx, sy, q = map(np.asarray, (population, sx, sy, q))
    labels = np.asarray(labels, dtype=int)
    mass = np.bincount(labels, weights=population)
    cx = np.bincount(labels, weights=sx) / np.where(mass > 0, mass, 1)
    cy = np.bincount(labels, weights=sy) / np.where(mass > 0, mass, 1)
    positive = population > 0
    px = sx[positive] / population[positive]
    py = sy[positive] / population[positive]
    distance = np.hypot(px - cx[labels[positive]], py - cy[labels[positive]])
    mean = np.average(distance, weights=population[positive])
    second = np.average(distance ** 2, weights=population[positive])
    within = np.sum(q[positive] - (sx[positive] ** 2 + sy[positive] ** 2) / population[positive]) / population.sum()
    if within < -1e-5:
        raise ValueError('Negative within-location inertia')
    exact = (q.sum() - np.sum(mass * (cx ** 2 + cy ** 2))) / population.sum()
    if not np.isclose(second + within, exact, rtol=1e-10, atol=1e-4):
        raise ValueError('Within/between variance decomposition failed')
    return {'mean_km': float(mean / 1000), 'sd_km': float(np.sqrt(max(0, second - mean ** 2)) / 1000),
            'centroid_rms_squared_km2': float(second / 1e6), 'within_location_km2': float(within / 1e6),
            'exact_rms_squared_km2': float(exact / 1e6)}


def diagnostic(array):
    return {name: finite_call(call) for name, call in {
        'rhat': lambda: az.rhat(array, method='rank'), 'bulk_ess': lambda: az.ess(array, method='bulk'),
        'tail_ess': lambda: az.ess(array, method='tail'), 'mcse_mean': lambda: az.mcse(array, method='mean'),
        'split_rhat': lambda: az.rhat(array, method='split'), 'folded_rhat': lambda: az.rhat(array, method='folded')}.items()}


def flatten(values):
    result = {}
    for name, item in values.items():
        result[name], result[name + '_status'] = item['value'], item['status']
    return result


def chain_analysis(table):
    """Full-history screens and exploratory attribution retain every chain."""
    measures = [*GEOGRAPHIC_METRICS, 'internal_boundary_km', 'common_cut_edges', 'sampler_cut_edges',
                'area_normalized_rms_radius', 'atom_centroid_mean_km', 'unit_centroid_mean_km']
    trends, windows, chains, omissions = [], [], [], []
    for state, state_table in table.groupby('state'):
        end = int(state_table.step.max()) + 1
        milestones = sorted(set([*range(5000, end + 1, 5000), end]))
        for (group, seed), chain in state_table.groupby(['group', 'seed']):
            chain = chain.sort_values('step')
            for metric in measures:
                x = chain[metric].to_numpy()
                split = len(x) // 2
                rows = {'state': state, 'group': group, 'seed': int(seed), 'metric': metric,
                        'mean': float(x.mean()), 'sd': float(x.std(ddof=1)), 'first_half_mean': float(x[:split].mean()),
                        'second_half_mean': float(x[split:].mean()), 'half_shift': float(x[split:].mean() - x[:split].mean())}
                for lag in (1, 5, 10, 50):
                    rows[f'acf_lag_{lag}_checkpoints'] = float(np.corrcoef(x[:-lag], x[lag:])[0, 1]) if len(x) > lag and np.std(x[:-lag]) > 0 and np.std(x[lag:]) > 0 else None
                chains.append(rows)
            for low in range(0, end, 5000):
                part = chain[(chain.step >= max(low, 500)) & (chain.step < low + 5000)]
                if len(part):
                    windows.append({'state': state, 'group': group, 'seed': int(seed), 'window_start': max(low, 500),
                                    'window_end_exclusive': min(low + 5000, end), 'checkpoints': len(part),
                                    **{metric: float(part[metric].mean()) for metric in measures}})
        for cohort in ['joint', *sorted(state_table.group.unique())]:
            selected = state_table if cohort == 'joint' else state_table[state_table.group == cohort]
            for length in milestones:
                part = selected[selected.step < length]
                for metric in measures:
                    arrays = np.stack([chain.sort_values('step')[metric].to_numpy() for _, chain in part.groupby(['group', 'seed'])])
                    threshold = max(400, arrays.shape[0] * 100)
                    values = diagnostic(arrays)
                    trends.append({'state': state, 'cohort': cohort, 'length': length, 'metric': metric,
                                   'chains': len(arrays), 'checkpoints_per_chain': arrays.shape[1], 'ess_threshold': threshold,
                                   'mean': float(arrays.mean()), **flatten(values)})
                    if length == end and len(arrays) > 2:
                        identities = list(part.groupby(['group', 'seed']).groups)
                        for i, (group, seed) in enumerate(identities):
                            omissions.append({'state': state, 'cohort': cohort, 'metric': metric, 'omitted_group': group,
                                              'omitted_seed': int(seed), 'interpretation': 'attribution_only_not_a_pass_or_selected_ensemble',
                                              **flatten(diagnostic(np.delete(arrays, i, axis=0)))})
    return trends, windows, chains, omissions


def run(root, cache, prior, mechanisms, output):
    if output.exists():
        raise FileExistsError(output)
    output.mkdir(parents=True)
    records = {}
    for path in [prior / 'results.json', prior / 'paired_presidential.csv', mechanisms / 'results.json', mechanisms / 'scores.csv', Path('paper/reviews/geographic-validation-20261109/validated/results.json')]:
        records[str(path)] = sha(path)
    original = json.loads((prior / 'results.json').read_text())
    for relative, expected in original['input_checksums'].items():
        if sha(root / relative) != expected:
            raise ValueError('Changed research input: ' + relative)
    table = pd.read_csv(prior / 'paired_presidential.csv')
    more = pd.read_csv(mechanisms / 'scores.csv')
    keys = ['state', 'group', 'seed', 'step', 'plan_hash']
    more = more[keys + [c for c in more.columns if c not in table.columns]]
    table = table.merge(more, on=keys, validate='one_to_one', how='outer', indicator=True)
    if not (table._merge == 'both').all():
        raise ValueError('Incomplete paired score coverage')
    table = table.drop(columns='_merge')
    all_rows, graph_records, edge_details, county_windows, centroid_rows, split_units = [], [], [], [], [], []
    for state in ('nc', 'tx'):
        master, _ = block_master(root, state)
        atoms = gpd.read_file(cache / f'{state}_atoms.gpkg', layer='atoms', ignore_geometry=True)
        point_file = np.load(cache / f'{state}_points.npz')
        if not np.array_equal(master.GEOID20.to_numpy(), point_file['geoids']):
            raise ValueError('Block order differs')
        inventory = json.loads(Path('paper/reviews/geographic-validation-20261109/validated/results.json').read_text())['measurement_inventory']['states'][state]
        for name in (f'{state}_atoms.gpkg', f'{state}_edges.npz', f'{state}_points.npz'):
            if sha(cache / name) != inventory['outputs'][name]:
                raise ValueError('Changed measurement cache')
            records[str(cache / name)] = sha(cache / name)
        edges = np.load(cache / f'{state}_edges.npz')
        left, right, length = edges['left'], edges['right'], edges['length']
        points, origin = point_file['coordinates'], point_file['origin']
        grouped, county_ids, county_names, atom_index, county_index = load_county_moments(root, state, master, points, origin, atoms, {})
        grouped_arrays = [grouped[name].to_numpy() for name in ['population', 'sx', 'sy', 'q']]
        specs = json.loads((root / MANIFESTS[state]).read_text())['experiments']
        unit_moments = atoms.groupby('unit', sort=True)[['population', 'sx', 'sy', 'q']].sum()
        for group, spec in specs.items():
            frame = gpd.read_file(root / spec['dataset'], layer='precincts')
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter('always')
                graph = Graph.from_geodataframe(frame)
            lookup = dict(zip(frame.UNIQUE_ID, range(len(frame))))
            atom_nodes = np.array([lookup[u] for u in atoms.unit])
            unit_nodes = np.array([lookup[u] for u in unit_moments.index])
            common, multiplicity, measurement_only, native_only, within = edge_partition(zip(left, right), atom_nodes, graph.edges)
            def pairs_array(pairs):
                return np.array(sorted(pairs), dtype=int).reshape(-1, 2)
            mp, npairs = pairs_array(measurement_only), pairs_array(native_only)
            graph_records.append({'state': state, 'group': group, 'units': len(frame), 'native_edges': len(graph.edges),
                                  'measurement_unit_edges': len(common), 'measurement_only_edges': len(measurement_only),
                                  'native_only_edges': len(native_only), 'within_unit_atomic_edges': within,
                                  'extra_between_unit_atomic_edges': sum(multiplicity.values()) - len(common),
                                  'warnings': [str(w.message) for w in caught], 'dataset_sha256': sha(root / spec['dataset'])})
            for role, pairs in [('measurement_only', measurement_only), ('native_only', native_only)]:
                for a, b in sorted(pairs):
                    edge_details.append({'state': state, 'group': group, 'role': role, 'first_unit': frame.iloc[a].UNIQUE_ID,
                                         'second_unit': frame.iloc[b].UNIQUE_ID,
                                         'native_shared_perimeter': graph.get_edge_data(a, b, {}).get('shared_perim'),
                                         'measurement_shared_boundary_km': float(length[((atom_nodes[left] == a) & (atom_nodes[right] == b)) | ((atom_nodes[left] == b) & (atom_nodes[right] == a))].sum() / 1000)})
            for seed in spec['seeds']:
                tag = f"{spec['epsilon']:g}".replace('.', 'p')
                dirs = [root / CAMPAIGN / group / 'checkpoints', root / 'outputs/analysis/rebuild_campaign_2026-11-02' / group / 'checkpoints']
                if group == 'tx_dispersed':
                    dirs = [root / CAMPAIGN / 'texas_independent_dispersed/checkpoints']
                sums = {}
                for base in table[(table.state == state) & (table.group == group) & (table.seed == seed) & (table.step >= 500)].to_dict('records'):
                    name = f"{spec['prefix']}_checkpoint_eps{tag}_seed{seed}_next{int(base['step']) + 1}.pkl"
                    paths = [d / name for d in dirs if (d / name).exists()]
                    actual = {sha(p) for p in paths}
                    expected = {original['input_checksums'][str(p.relative_to(root))] for p in paths if str(p.relative_to(root)) in original['input_checksums']}
                    if not paths or len(actual) != 1 or actual != expected:
                        raise ValueError('Missing or changed checkpoint')
                    with paths[0].open('rb') as stream:
                        checkpoint = pickle.load(stream)
                    if checkpoint['plan_hash'] != base['plan_hash']:
                        raise ValueError('Plan identity differs')
                    assignment = np.array([checkpoint['assignment'][node] for node in range(len(frame))], dtype=int)
                    if assignment_hash(checkpoint['assignment'], graph.edges) != base['plan_hash']:
                        raise ValueError('Native graph assignment fingerprint differs')
                    labels = assignment[atom_nodes]
                    native_cuts = sum(assignment[a] != assignment[b] for a, b in graph.edges)
                    if native_cuts != base['sampler_cut_edges']:
                        raise ValueError('Native cut count differs from saved CSV')
                    extra = sum((count - 1) for (a, b), count in multiplicity.items() if assignment[a] != assignment[b])
                    added = int(np.sum(assignment[mp[:, 0]] != assignment[mp[:, 1]]))
                    removed = int(np.sum(assignment[npairs[:, 0]] != assignment[npairs[:, 1]]))
                    if base['common_cut_edges'] != native_cuts + extra + added - removed:
                        raise ValueError('Graph/count decomposition failed')
                    a = centroid_radial(*[atoms[c].to_numpy() for c in ['population', 'sx', 'sy', 'q']], labels)
                    u = centroid_radial(*[unit_moments[c].to_numpy() for c in ['population', 'sx', 'sy', 'q']], assignment[unit_nodes])
                    if not np.isclose(a['exact_rms_squared_km2'], base['rms_distance_km'] ** 2, rtol=1e-10) or not np.isclose(a['exact_rms_squared_km2'], u['exact_rms_squared_km2'], rtol=1e-10):
                        raise ValueError('Block/centroid moment identity differs')
                    if max(a['mean_km'], u['mean_km']) > base['mean_distance_km'] + 1e-8:
                        raise ValueError('Collapsed mean violates convexity bound')
                    row = {**base, 'atom_centroid_mean_km': a['mean_km'], 'unit_centroid_mean_km': u['mean_km'],
                           'atomic_multiplicity_cut_excess': extra, 'measurement_only_cuts': added, 'native_only_cuts': removed}
                    all_rows.append(row)
                    centroid_rows.append({k: row[k] for k in keys} | {'block_mean_km': base['mean_distance_km'],
                        **{'atom_' + k: v for k, v in a.items()}, **{'unit_' + k: v for k, v in u.items()}})
                    contribution = county_contributions(*grouped_arrays, county_index, atom_index, labels, atoms)
                    if not np.isclose(contribution.sum(), base['normalized_rms_radius'] ** 2, rtol=1e-10):
                        raise ValueError('County sum failed')
                    window = int(base['step']) // 5000
                    if window not in sums:
                        sums[window] = [0, np.zeros(len(county_ids))]
                    sums[window][0] += 1
                    sums[window][1] += contribution
                for window, (count, values) in sums.items():
                    for county, value in zip(county_ids, values / count):
                        county_windows.append({'state': state, 'group': group, 'seed': seed, 'window_start': max(500, window * 5000),
                                               'window_end_exclusive': min(spec['steps'], (window + 1) * 5000), 'checkpoints': count,
                                               'county_fips': county, 'county': county_names[county], 'mean_squared_radius_contribution': float(value)})
                print(state, group, seed, 'complete', flush=True)
        for base in table[(table.state == state) & table.group.str.startswith('enacted')].to_dict('records'):
            labels = atoms['enacted_' + base['group'].split('_')[-1]].to_numpy()
            a = centroid_radial(*[atoms[c].to_numpy() for c in ['population', 'sx', 'sy', 'q']], labels)
            split = atoms.assign(label=labels).groupby('unit').label.nunique() > 1
            split_units.append({'state': state, 'group': base['group'], 'split_simulation_units': int(split.sum()),
                                'population_in_split_units': int(unit_moments.loc[split[split].index].population.sum()),
                                'block_mean_km': base['mean_distance_km'], 'atom_centroid_mean_km': a['mean_km'],
                                'unit_centroid_status': 'unavailable_assignment_splits_units' if split.any() else 'representable',
                                'atom_within_location_km2': a['within_location_km2']})
    scores = pd.DataFrame(all_rows)
    scores.to_csv(output / 'scores.csv', index=False)
    pd.DataFrame(centroid_rows).to_csv(output / 'centroid_resolution.csv', index=False)
    pd.DataFrame(edge_details, columns=['state', 'group', 'role', 'first_unit', 'second_unit', 'native_shared_perimeter', 'measurement_shared_boundary_km']).to_csv(output / 'graph_edge_differences.csv', index=False)
    pd.DataFrame(county_windows).to_csv(output / 'county_windows.csv', index=False)
    trends, windows, chains, omissions = chain_analysis(scores)
    for name, values in [('diagnostic_trends', trends), ('chain_windows', windows), ('chain_summary', chains), ('leave_one_out_attribution', omissions)]:
        pd.DataFrame(values).to_csv(output / (name + '.csv'), index=False)
    result = {'research_ready': False, 'freeze_changed': False, 'sampler_changed': False,
              'checkpoint_interval': 100, 'warmup': 500, 'graphs': graph_records, 'enacted_resolution': split_units,
              'input_hashes': records, 'code_sha256': sha(__file__), 'source_input_hashes_checked': len(original['input_checksums']),
              'runtime': {'python': sys.version, 'platform': platform.platform(), 'nice': os.getpriority(os.PRIO_PROCESS, 0),
                          'packages': {name: metadata.version(name) for name in ['arviz', 'numpy', 'pandas', 'geopandas', 'gerrychain']}},
              'sampler_sha256': sha(root / 'src/chain/run_ensemble.py'),
              'checkpoint_code_sha256': sha(root / 'src/chain/checkpoint_integrity.py'),
              'checks': {'matched_assignments': len(scores), 'native_and_common_cut_decompositions': len(scores),
                         'within_between_inertia_identities': len(scores) * 2, 'county_sum_identities': len(scores)},
              'scope': 'No assignment is changed. Leave-one-out diagnostics attribute disagreement and never replace full-cohort screens. Unit and atom centroids are explicitly collapsed-location sensitivity measurements, not replacements for block-level scores.'}
    (output / 'results.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['source-root', 'measurement-cache', 'parallel-review', 'mechanism-review', 'output-dir']:
        parser.add_argument('--' + name, type=Path, required=True)
    a = parser.parse_args()
    run(a.source_root.resolve(), a.measurement_cache, a.parallel_review, a.mechanism_review, a.output_dir)


if __name__ == '__main__':
    main()
