"""Verify same-map comparisons and independently tally every existing election."""

import argparse
import json
from pathlib import Path
import pickle
import warnings

import arviz as az
import geopandas as gpd
from gerrychain import Graph
import numpy as np
import pandas as pd

from paper.frozen_elections import MANIFESTS
from paper.geographic_clustering import CAMPAIGN, sha
from paper.parallel_analysis import GEOGRAPHIC_METRICS, DISTANCE_METRICS, association
from paper.review_precision import finite_call, half_comparison
from paper.score_checkpoint_elections import load_votes
from paper.validate_checkpoint_elections import assignment_hash


def independent_election_tally(votes, labels, districts):
    labels = np.asarray(labels, dtype=int)
    if votes.ndim != 3 or votes.shape[2] != 2 or len(votes) != len(labels) or set(labels) != set(range(1, districts + 1)):
        raise ValueError('Invalid election units or district labels')
    return [int(np.sum(np.bincount(labels, weights=votes[:, index, 0], minlength=districts + 1)[1:] > np.bincount(labels, weights=votes[:, index, 1], minlength=districts + 1)[1:])) for index in range(votes.shape[1])]


def check(root, directory):
    target = directory / 'verification.json'
    if target.exists():
        raise FileExistsError(target)
    result = json.loads((directory / 'results.json').read_text())
    if result['code_sha256'] != sha('paper/parallel_analysis.py'):
        raise ValueError('Distance analysis code changed')
    for relative, expected in result['input_checksums'].items():
        if sha(root / relative) != expected:
            raise ValueError(f'Changed research input: {relative}')
    for path, expected in result['linked_inputs'].items():
        if sha(path) != expected:
            raise ValueError(f'Changed linked analysis: {path}')
    table = pd.read_csv(directory / 'paired_presidential.csv')
    actual = table[table.group.str.startswith('enacted')]
    retained = table[(~table.group.str.startswith('enacted')) & (table.step >= 500)]
    if not np.isfinite(table[list(DISTANCE_METRICS) + ['rms_distance_km']].to_numpy()).all():
        raise ValueError('Undefined distance measure')
    if not np.allclose(table.distance_cv * table.inverse_distance_cv, 1, rtol=1e-12, atol=1e-12):
        raise ValueError('CV reciprocal identity failed')
    if not np.allclose(table.rms_distance_km ** 2, table.mean_distance_km ** 2 + table.sd_distance_km ** 2, rtol=1e-12, atol=1e-8):
        raise ValueError('Mean/SD/RMS identity failed')
    for state, length, chains in [('tx', 70000, 8), ('nc', 23000, 6)]:
        selected = table[(table.state == state) & (~table.group.str.startswith('enacted'))]
        if selected.groupby(['group', 'seed']).ngroups != chains:
            raise ValueError('Missing chain')
        for _, chain in selected.groupby(['group', 'seed']):
            if chain.sort_values('step').step.astype(int).tolist() != list(range(99, length, 100)):
                raise ValueError('Missing or overlapping checkpoint observations')
    support = []
    for row in actual.to_dict('records'):
        values = retained[retained.state == row['state']]
        for metric in GEOGRAPHIC_METRICS:
            low, high = float(values[metric].min()), float(values[metric].max())
            support.append({'state': row['state'], 'enacted': row['group'], 'metric': metric, 'value': row[metric], 'minimum': low, 'maximum': high, 'inside_observed_range': low <= row[metric] <= high})
    pd.DataFrame(support).to_csv(directory / 'geographic_support.csv', index=False)
    full_dir = directory / 'full_elections'
    full = json.loads((full_dir / 'results.json').read_text())
    receipt = json.loads((full_dir / 'assignment_validation.json').read_text())
    if receipt['results_sha256'] != sha(full_dir / 'results.json') or full['code_sha256'] != sha('paper/frozen_elections.py'):
        raise ValueError('Full-election scoring evidence changed')
    full_rows = pd.DataFrame(json.loads((full_dir / 'checkpoint_scores.json').read_text()))
    keys = ['state', 'group', 'seed', 'step', 'plan_hash']
    if full_rows.duplicated(keys).any() or retained.duplicated(keys).any():
        raise ValueError('Duplicate paired map identity')
    merged = full_rows.merge(retained, on=keys, how='outer', validate='one_to_one', indicator=True)
    if not (merged._merge == 'both').all() or not np.array_equal(merged.President, merged.democratic_seats_2024_presidential_model):
        raise ValueError('Full election/geography pairing differs')
    merged = merged.drop(columns='_merge')
    merged.to_csv(directory / 'paired_all_elections.csv', index=False)
    old = pd.DataFrame(json.loads(Path('paper/election-sensitivity/checkpoint_scores.json').read_text()))
    old_index = old.set_index(keys)
    new_index = full_rows.set_index(keys)
    legacy_cells = 0
    for state, values in old.groupby('state'):
        offices = [item['office'] for item in full['results'][state]['models']]
        subset = values.set_index(keys)
        if not np.array_equal(subset[offices].to_numpy(), new_index.loc[subset.index, offices].to_numpy()):
            raise ValueError('An earlier election score changed')
        legacy_cells += len(values) * len(offices)
    tally_checks = 0
    warmup_rows, warmup_graph_warnings = [], []
    for state, relative in MANIFESTS.items():
        specs = json.loads((root / relative).read_text())['experiments']
        vote_cache = {}
        for group, spec in specs.items():
            if spec['dataset_sha256'] not in vote_cache:
                records = {}
                votes, models, enacted, inventory = load_votes(root, state, root / spec['dataset'], records)
                for name, expected in records.items():
                    if full['input_checksums'].get(name) != expected:
                        raise ValueError('Independent election aggregation provenance differs')
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter('always')
                    graph = Graph.from_geodataframe(gpd.read_file(root / spec['dataset'], layer='precincts'))
                warmup_graph_warnings.extend({'dataset': spec['dataset'], 'message': str(item.message)} for item in caught)
                vote_cache[spec['dataset_sha256']] = votes, models, graph
            votes, models, graph = vote_cache[spec['dataset_sha256']]
            offices = [item['office'] for item in models]
            directories = [root / CAMPAIGN / group / 'checkpoints', root / 'outputs/analysis/rebuild_campaign_2026-11-02' / group / 'checkpoints']
            if group == 'tx_dispersed':
                directories = [root / CAMPAIGN / 'texas_independent_dispersed/checkpoints']
            tag = f"{spec['epsilon']:g}".replace('.', 'p')
            selected = full_rows[(full_rows.state == state) & (full_rows.group == group)]
            for row in selected.to_dict('records'):
                boundary, seed = int(row['step']) + 1, int(row['seed'])
                name = f"{spec['prefix']}_checkpoint_eps{tag}_seed{seed}_next{boundary}.pkl"
                paths = [folder / name for folder in directories if (folder / name).is_file()]
                if not paths:
                    raise ValueError('Missing tally checkpoint')
                with paths[0].open('rb') as stream:
                    checkpoint = pickle.load(stream)
                if checkpoint['plan_hash'] != row['plan_hash']:
                    raise ValueError('Independent tally plan identity differs')
                counts = independent_election_tally(votes, [checkpoint['assignment'][node] for node in range(len(votes))], spec['districts'])
                if counts != [row[office] for office in offices]:
                    raise ValueError('Independent statewide election tally differs')
                tally_checks += len(offices)
            for seed in spec['seeds']:
                reference_name = f"{spec['prefix']}_checkpoint_eps{tag}_seed{seed}_next600.pkl"
                reference_path = next(folder / reference_name for folder in directories if (folder / reference_name).is_file())
                with reference_path.open('rb') as stream:
                    reference = pickle.load(stream)
                for boundary in range(100, 501, 100):
                    name = f"{spec['prefix']}_checkpoint_eps{tag}_seed{seed}_next{boundary}.pkl"
                    paths = [folder / name for folder in directories if (folder / name).is_file()]
                    if not paths or sha(paths[0]) != result['input_checksums'].get(str(paths[0].relative_to(root))):
                        raise ValueError('Missing or changed warmup checkpoint')
                    with paths[0].open('rb') as stream:
                        checkpoint = pickle.load(stream)
                    expected_row = table[(table.state == state) & (table.group == group) & (table.seed == seed) & (table.step == boundary - 1)]
                    if len(expected_row) != 1 or checkpoint['plan_hash'] != expected_row.plan_hash.item() or checkpoint['provenance'] != reference['provenance'] or checkpoint['seed'] != seed or checkpoint['next_step'] != boundary:
                        raise ValueError('Warmup checkpoint identity differs')
                    if assignment_hash(checkpoint['assignment'], graph.edges) != checkpoint['plan_hash']:
                        raise ValueError('Warmup assignment fingerprint differs')
                    counts = independent_election_tally(votes, [checkpoint['assignment'][node] for node in range(len(votes))], spec['districts'])
                    if counts[offices.index('President')] != expected_row.democratic_seats_2024_presidential_model.item():
                        raise ValueError('Warmup presidential score differs')
                    warmup_rows.append({'state': state, 'group': group, 'seed': seed, 'step': boundary - 1, 'plan_hash': checkpoint['plan_hash'], **dict(zip(offices, counts))})
            print(state, group, 'independent tallies complete', flush=True)
    pd.DataFrame(warmup_rows).to_csv(directory / 'election_warmup_checkpoints.csv', index=False)
    complete_elections = pd.concat([full_rows, pd.DataFrame(warmup_rows)], ignore_index=True)
    associations, election_diagnostics, election_halves, election_warmups, responsiveness = [], [], [], [], []
    for state, values in merged.groupby('state'):
        models = full['results'][state]['models']
        inventory = full['results'][state]['inventory']
        for cohort in ['joint', *sorted(values.group.unique())]:
            selected = values if cohort == 'joint' else values[values.group == cohort]
            for index, model in enumerate(models):
                office = model['office']
                array = np.stack([chain.sort_values('step')[office].to_numpy() for _, chain in selected.groupby(['group', 'seed'])])
                election_diagnostics.append({'state': state, 'cohort': cohort, 'election': office, 'chains': array.shape[0], 'checkpoints_per_chain': array.shape[1], 'mean': float(array.mean()), 'rhat': finite_call(lambda: az.rhat(array, method='rank')), 'bulk_ess': finite_call(lambda: az.ess(array, method='bulk')), 'tail_ess': finite_call(lambda: az.ess(array, method='tail')), 'mcse_mean': finite_call(lambda: az.mcse(array, method='mean'))})
                election_halves.append({'state': state, 'cohort': cohort, 'election': office, **half_comparison(array)})
                for metric in GEOGRAPHIC_METRICS:
                    for scope, part in [('pooled', selected), *[(f'seed_{int(seed)}', chain) for (_, seed), chain in selected.groupby(['group', 'seed'])]]:
                        associations.append({'state': state, 'cohort': cohort, 'election': office, 'metric': metric, 'scope': scope, **association(part[metric], part[office])})
                if cohort == 'joint':
                    dem, rep = [inventory['statewide_votes'][column] for column in model['columns']]
                    responsiveness.append({'state': state, 'election': office, 'statewide_democratic_two_party_share': dem / (dem + rep), 'checkpoints': array.size, 'median': float(np.median(array)), 'mean': float(array.mean()), 'minimum': int(array.min()), 'maximum': int(array.max()), 'enacted': {year: seats[index] for year, seats in full['results'][state]['enacted_seats'].items()}})
    for state, values in complete_elections.groupby('state'):
        for cohort in ['joint', *sorted(values.group.unique())]:
            selected = values if cohort == 'joint' else values[values.group == cohort]
            for warmup in (0, 250, 500, 1000):
                for model in full['results'][state]['models']:
                    office = model['office']
                    array = np.stack([chain.sort_values('step')[office].to_numpy() for _, chain in selected[selected.step >= warmup].groupby(['group', 'seed'])])
                    election_warmups.append({'state': state, 'cohort': cohort, 'election': office, 'warmup': warmup, 'mean': float(array.mean()), 'rhat': finite_call(lambda: az.rhat(array, method='rank')), 'bulk_ess': finite_call(lambda: az.ess(array, method='bulk')), 'tail_ess': finite_call(lambda: az.ess(array, method='tail')), 'mcse_mean': finite_call(lambda: az.mcse(array, method='mean'))})
    pd.DataFrame(associations).to_csv(directory / 'all_election_associations.csv', index=False)
    q = {'full_election_rows': len(merged), 'independent_election_tallies': tally_checks, 'legacy_election_score_cells_reproduced': legacy_cells,
         'geographic_support': support, 'responsiveness': responsiveness, 'election_diagnostics': election_diagnostics, 'election_halves': election_halves, 'election_warmups': election_warmups,
         'paired_scores_sha256': sha(directory / 'paired_all_elections.csv'), 'research_ready': False}
    (directory / 'paired_election_results.json').write_text(json.dumps(q, indent=2, allow_nan=False) + '\n')
    diagnostic_values = [item[key] for item in result['diagnostics'] for key in ['rhat', 'bulk_ess', 'tail_ess', 'mcse_mean']]
    election_values = [item[key] for item in election_diagnostics for key in ['rhat', 'bulk_ess', 'tail_ess', 'mcse_mean']]
    verification = {'input_hashes_checked': len(result['input_checksums']), 'matched_primary_checkpoints': len(retained), 'matched_full_election_checkpoints': len(merged),
                    'independent_election_tallies': tally_checks, 'legacy_election_score_cells_reproduced': legacy_cells, 'direct_radial_identities_checked': len(table), 'prewarmup_election_assignments_verified': len(warmup_rows), 'prewarmup_graph_warnings': warmup_graph_warnings,
                    'unavailable_distance_diagnostics': sum(item['status'] != 'finite' for item in diagnostic_values),
                    'unavailable_election_diagnostics': sum(item['status'] != 'finite' for item in election_values),
                    'sampler_sha256': sha(root / 'src/chain/run_ensemble.py'), 'checkpoint_code_sha256': sha(root / 'src/chain/checkpoint_integrity.py'),
                    'research_ready': False}
    target.write_text(json.dumps(verification, indent=2, allow_nan=False) + '\n')
    print(json.dumps(verification, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--review-dir', type=Path, required=True)
    args = parser.parse_args()
    check(args.source_root.resolve(), args.review_dir)


if __name__ == '__main__':
    main()
