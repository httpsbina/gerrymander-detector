"""Score all locally available statewide elections on the full frozen checkpoint set."""

import argparse
import json
import os
from pathlib import Path
import pickle
from types import SimpleNamespace
import warnings

import geopandas as gpd
from gerrychain import Graph

from paper.geographic_clustering import CAMPAIGN, sha
from paper.score_checkpoint_elections import load_votes, score_group
from paper.validate_checkpoint_elections import assignment_hash
from src.chain.checkpoint_integrity import provenance


MANIFESTS = {'tx': CAMPAIGN / 'tx_shared45000_continuation_20261103/shared_070000/manifest.json',
             'nc': CAMPAIGN / 'nc_primary_continuation/snapshot_003/manifest.json'}


def score(root, output):
    if output.exists():
        raise FileExistsError(output)
    output.mkdir(parents=True)
    records, results, plans = {}, {}, []
    for state, relative in MANIFESTS.items():
        records[str(relative)] = sha(root / relative)
        specs = json.loads((root / relative).read_text())['experiments']
        groups, models, enacted, inventory = {}, None, None, None
        for group, spec in specs.items():
            votes, current_models, current_enacted, current_inventory = load_votes(root, state, root / spec['dataset'], records)
            if models is not None and (models != current_models or enacted != current_enacted):
                raise ValueError('Inconsistent statewide election definitions')
            models, enacted, inventory = current_models, current_enacted, current_inventory
            values, scored = score_group(root, group, spec, votes, models, enacted, records)
            groups[group] = values
            plans.extend({'state': state, **plan} for plan in scored)
        results[state] = {'models': models, 'enacted_seats': enacted, 'inventory': inventory, 'groups': groups}
    report = {'process_nice': os.getpriority(os.PRIO_PROCESS, 0), 'checkpoint_interval': 100,
              'state_definition': 'Checkpoint next_step N contains recorded state N-1. All saved frozen 100-state checkpoints after warmup 500 are used.',
              'results': results, 'input_checksums': records, 'code_sha256': sha(__file__)}
    (output / 'results.json').write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    (output / 'checkpoint_scores.json').write_text(json.dumps(plans, indent=2, allow_nan=False) + '\n')
    print(output, 'scoring complete', flush=True)


def audit(root, directory):
    target = directory / 'assignment_validation.json'
    if target.exists():
        raise FileExistsError(target)
    report = json.loads((directory / 'results.json').read_text())
    graphs, expected, checked, geometry_warnings, runtime_profiles = {}, {}, 0, [], []
    for relative, checksum in report['input_checksums'].items():
        path = root / relative
        if sha(path) != checksum:
            raise ValueError(f'Changed input: {relative}')
        if path.suffix != '.pkl':
            continue
        with path.open('rb') as stream:
            checkpoint = pickle.load(stream)
        recorded = checkpoint['provenance']
        candidates = [name for name, value in report['input_checksums'].items() if value == recorded['dataset_sha256'] and name.endswith('.gpkg')]
        if len(candidates) != 1:
            raise ValueError('Ambiguous checkpoint geography')
        dataset = root / candidates[0]
        if recorded['dataset_sha256'] not in graphs:
            frame = gpd.read_file(dataset, layer=recorded['configuration']['layer'])
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter('always')
                graphs[recorded['dataset_sha256']] = Graph.from_geodataframe(frame)
            geometry_warnings.extend({'dataset': candidates[0], 'message': str(item.message)} for item in caught)
        graph = graphs[recorded['dataset_sha256']]
        key = json.dumps(recorded, sort_keys=True)
        if key not in expected:
            expected[key] = provenance(SimpleNamespace(**recorded['configuration'], dataset=dataset), graph, root / 'src/chain/run_ensemble.py')
            current_runtime = expected[key]['runtime']
            if current_runtime['python'] != recorded['runtime']['python'] or current_runtime['packages'] != recorded['runtime']['packages']:
                raise ValueError('Read-only scoring runtime Python or packages differ from recorded profile')
            runtime_profiles.append({'recorded': recorded['runtime'], 'analysis': current_runtime, 'platform_equal': recorded['runtime']['platform'] == current_runtime['platform']})
        if checkpoint.get('version') != 2 or not isinstance(checkpoint.get('seed'), int) or not isinstance(checkpoint.get('next_step'), int) or checkpoint['next_step'] < 1:
            raise ValueError('Invalid checkpoint identity')
        for field in ['dataset_sha256', 'graph_sha256', 'runner_sha256', 'checkpoint_code_sha256', 'configuration']:
            if recorded[field] != expected[key][field]:
                raise ValueError(f'Changed checkpoint evidence: {field}')
        if set(checkpoint['assignment']) != set(graph.nodes):
            raise ValueError('Checkpoint node coverage differs')
        if assignment_hash(checkpoint['assignment'], graph.edges) != checkpoint['plan_hash']:
            raise ValueError('Assignment fingerprint differs')
        checked += 1
    receipt = {'analysis_only': True, 'replay_performed': False, 'continuation_certified': False,
               'checkpoints_verified': checked, 'distinct_datasets': len(graphs), 'results_sha256': sha(directory / 'results.json'),
               'validation_code_sha256': sha(__file__), 'runtime_profiles': runtime_profiles, 'geometry_warnings': geometry_warnings,
               'checks': ['all input hashes', 'checkpoint identity', 'dataset and graph fingerprints', 'sampler and checkpoint code', 'configuration', 'assignment cut-edge fingerprint', 'same Python build and packages'],
               'platform_scope': 'Platform strings are recorded separately for deterministic read-only assignment scoring. This audit does not relax continuation or exact-replay requirements.'}
    target.write_text(json.dumps(receipt, indent=2, allow_nan=False) + '\n')
    print('Assignment checks:', checked, 'datasets:', len(graphs), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--audit-only', action='store_true')
    args = parser.parse_args()
    if args.audit_only:
        audit(args.source_root.resolve(), args.output_dir)
    else:
        score(args.source_root.resolve(), args.output_dir)


if __name__ == '__main__':
    main()
