"""Validate all frozen boundaries and prepare isolated continuation segments."""
import argparse
import copy
import csv
from importlib import metadata
import json
from pathlib import Path
import pickle
import sys

from paper.geographic_clustering import sha
MANIFESTS = {'tx': Path('outputs/analysis/convergence_campaign_2026-11-02/tx_shared45000_continuation_20261103/shared_070000/manifest.json'),
             'nc': Path('outputs/analysis/convergence_campaign_2026-11-02/nc_primary_continuation/snapshot_003/manifest.json')}


def prepare(root, prior, destination):
    destination.resolve().relative_to(root)
    if destination.exists():
        raise FileExistsError(destination)
    records = json.loads((prior / 'results.json').read_text())['input_checksums']
    for name, expected in records.items():
        if sha(root / name) != expected:
            raise ValueError('Changed input: ' + name)
    for line in (root / 'requirements-research-macos-arm64-py312.txt').read_text().splitlines():
        if line and not line.startswith('#'):
            name, version = line.split('==')
            if metadata.version(name) != version:
                raise ValueError('Pinned package differs: ' + name)
    sys.path.insert(0, str(root))
    from src.chain.continue_on_target import verify_cohort, ROOT
    if ROOT != root:
        raise ValueError('Continuation helper loaded from the wrong checkout')
    destination.mkdir(parents=True)
    checkpoint_index = {}
    for name in records:
        if name.endswith('.pkl'):
            checkpoint_index.setdefault(Path(name).name, []).append(root / name)
    experiments, source_code, sources = {}, None, {}
    for state, relative in MANIFESTS.items():
        manifest = json.loads((root / relative).read_text())
        if source_code is not None and source_code != manifest['source_code']:
            raise ValueError('Different baseline implementations')
        source_code = manifest['source_code']
        for key, original in manifest['experiments'].items():
            e = copy.deepcopy(original)
            stage = destination / 'source_histories' / key
            ensembles, checkpoints = stage / 'ensembles', stage / 'checkpoints'
            ensembles.mkdir(parents=True)
            checkpoints.mkdir()
            for seed in e['seeds']:
                tag = f"{e['epsilon']:g}".replace('.', 'p')
                seen = set()
                for path in sorted((root / e['input_dir']).glob(f"{e['prefix']}_chain_eps{tag}_seed{seed}_steps*.csv")):
                    with path.open() as stream:
                        for row in csv.DictReader(stream):
                            step = int(row['step'])
                            if step in seen or not 0 <= step < e['steps'] or int(row['seed']) != seed:
                                raise ValueError('Overlapping or out-of-bound source history')
                            seen.add(step)
                    sources[str(path.relative_to(root))] = sha(path)
                    (ensembles / path.name).symlink_to(path)
                if seen != set(range(e['steps'])):
                    raise ValueError('Incomplete source history')
                for boundary in range(100, e['steps'] + 1, 100):
                    name = f"{e['prefix']}_checkpoint_eps{tag}_seed{seed}_next{boundary}.pkl"
                    paths = checkpoint_index[name]
                    if len({sha(p) for p in paths}) != 1:
                        raise ValueError('Conflicting source checkpoint copies')
                    with paths[0].open('rb') as stream:
                        c = pickle.load(stream)
                    if c['seed'] != seed or c['next_step'] != boundary:
                        raise ValueError('Checkpoint boundary differs')
                    (checkpoints / name).symlink_to(paths[0])
                    sources[str(paths[0].relative_to(root))] = sha(paths[0])
            e['input_dir'] = str(ensembles.relative_to(root))
            configs = {}
            for seed in e['seeds']:
                old = e.get('seed_configs', {}).get(str(seed), e['config'])
                config = json.loads((root / old).read_text())
                plan = config['states'][e['state']]['plans'][e['starting_plan']]
                plan['output_dir'], plan['checkpoint_dir'] = e['input_dir'], str(checkpoints.relative_to(root))
                target = stage / f'seed{seed}.json'
                target.write_text(json.dumps(config, indent=2) + '\n')
                configs[str(seed)] = str(target.relative_to(root))
            e['seed_configs'] = configs
            e['config'] = configs[str(e['seeds'][0])]
            experiments[key] = e
    for name, expected in source_code.items():
        if sha(root / name) != expected:
            raise ValueError('Sampling source changed')
    converted, replays, cache = {}, [], {}
    for key, e in experiments.items():
        value, receipt = verify_cohort(key, e, destination / 'verification' / key, 4, cache)
        converted[key] = value
        replays.extend(receipt)
        print(key, 'replay validated', json.dumps(receipt), flush=True)
    result = {'source_code': source_code, 'experiments': converted, 'original_experiments': experiments,
              'source_files': sources, 'replay': replays, 'code_sha256': sha(__file__)}
    (destination / 'manifest.json').write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['source-root', 'parallel-review', 'output-dir']:
        parser.add_argument('--' + name, type=Path, required=True)
    a = parser.parse_args()
    prepare(a.source_root.resolve(), a.parallel_review, a.output_dir.resolve())
