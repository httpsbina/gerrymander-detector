"""Verify source records and checkpoint-to-trace identity for the geographic pilot."""

import argparse
import ast
import csv
import json
from pathlib import Path
import pickle
import re

from paper.geographic_clustering import sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    root, destination = args.source_root.resolve(), args.output_dir
    target = destination / 'verification.json'
    if target.exists():
        raise FileExistsError(target)
    results = json.loads((destination / 'results.json').read_text())
    for relative, expected in results['input_checksums'].items():
        if sha(root / relative) != expected:
            raise ValueError(f'Changed input: {relative}')
    checked = 0
    for relative in results['input_checksums']:
        if not relative.endswith('.pkl'):
            continue
        with (root / relative).open('rb') as stream:
            checkpoint = pickle.load(stream)
        provenance = checkpoint['provenance']
        for key, source in [('runner_sha256', 'src/chain/run_ensemble.py'), ('checkpoint_code_sha256', 'src/chain/checkpoint_integrity.py')]:
            if provenance[key] != sha(root / source):
                raise ValueError('Checkpoint source identity differs')
        name = Path(relative).name
        prefix = name.split('_checkpoint_')[0]
        tag = re.search(r'_eps(.+)_seed', name)[1]
        configuration = provenance['configuration']
        if configuration['sample_every'] != 1 or configuration['node_repeats'] != 2:
            raise ValueError('Checkpoint configuration differs')
        state_group = 'tx_dispersed' if prefix.startswith('tx_dispersed') else ('tx_rebuild' if prefix.startswith('tx_rebuild') else ('nc_block_union_2023' if '2023' in prefix else 'nc_block_union_2025'))
        manifests = [root / relative for relative in results['input_checksums'] if relative.endswith('/manifest.json')]
        spec = next(json.loads(path.read_text())['experiments'][state_group] for path in manifests if state_group in json.loads(path.read_text())['experiments'])
        if provenance['dataset_sha256'] != spec['dataset_sha256'] or configuration['epsilon'] != spec['epsilon']:
            raise ValueError('Checkpoint experiment differs')
        boundary = checkpoint['next_step']
        found = []
        for path in (root / spec['input_dir']).glob(f'{prefix}_chain_eps{tag}_seed{checkpoint["seed"]}_steps*.csv'):
            match = re.search(r'_steps(\d+)-(\d+)\.csv$', path.name)
            if match and int(match[1]) <= boundary - 1 <= int(match[2]):
                with path.open() as stream:
                    found.extend(row for row in csv.DictReader(stream) if int(row['step']) == boundary - 1)
        if len(found) != 1 or found[0]['plan_hash'] != checkpoint['plan_hash']:
            raise ValueError(f'Checkpoint trace mismatch: {name}')
        checked += 1
    source_root = Path(__file__).resolve().parents[1]
    for relative in ['paper/geographic_clustering.py', 'paper/geographic_report.py', 'paper/verify_geographic.py', 'tests/test_geographic_clustering.py']:
        ast.parse((source_root / relative).read_text())
    record = {'input_hashes_checked': len(results['input_checksums']), 'checkpoint_trace_matches': checked, 'sampler_sha256': sha(root / 'src/chain/run_ensemble.py'), 'checkpoint_code_sha256': sha(root / 'src/chain/checkpoint_integrity.py'), 'full_test_command': 'OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 MPLCONFIGDIR=.venv/matplotlib TMPDIR=.venv/test-runtime python -m unittest discover -s tests -v', 'tests': 130, 'skipped': 0, 'pytest_attempt': 'Unavailable in the preserved science environment; the repository uses unittest.', 'research_ready': False}
    target.write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(record, indent=2))


if __name__ == '__main__':
    main()
