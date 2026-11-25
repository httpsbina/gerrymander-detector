"""Verify preserved freezes and independently match the attribution records."""

import argparse
import ast
import json
from pathlib import Path
import re

import numpy as np
import pandas as pd

from paper.geographic_clustering import sha


def check(root, directory, reproduced, prior):
    target = directory / 'verification.json'
    if target.exists():
        raise FileExistsError(target)
    result = json.loads((directory / 'results.json').read_text())
    for name, expected in result['input_hashes'].items():
        if sha(name) != expected:
            raise ValueError('Changed analysis input: ' + name)
    for filename, code in [('results.json', 'paper/geographic_mixing.py'),
                           ('unit_support.json', 'paper/geographic_unit_support.py'),
                           ('mean_distance_county_verification.json', 'paper/geographic_mean_drivers.py')]:
        if json.loads((directory / filename).read_text())['code_sha256'] != sha(code):
            raise ValueError('Analysis source changed after execution')
    frozen = {}
    for name in ['nc-baseline-freeze-23000', 'texas-baseline-freeze-70000']:
        manifest_path = Path('deliverables') / name / 'freeze_manifest.json'
        manifest = json.loads(manifest_path.read_text())
        failures = [f for f, checksum in manifest['checksums'].items() if not (root / f).is_file() or sha(root / f) != checksum]
        if failures:
            raise ValueError('Frozen checksums differ: ' + repr(failures))
        frozen[name] = {'checked': len(manifest['checksums']), 'failures': [], 'manifest_sha256': sha(manifest_path)}
    scores = pd.read_csv(directory / 'scores.csv')
    before = pd.read_csv(prior / 'paired_presidential.csv')
    before = before[(~before.group.str.startswith('enacted')) & (before.step >= 500)]
    keys = ['state', 'group', 'seed', 'step', 'plan_hash']
    if scores.duplicated(keys).any() or set(map(tuple, scores[keys].to_numpy())) != set(map(tuple, before[keys].to_numpy())):
        raise ValueError('Incomplete or duplicate saved assignments')
    if not np.allclose(scores.common_cut_edges, scores.sampler_cut_edges + scores.atomic_multiplicity_cut_excess + scores.measurement_only_cuts - scores.native_only_cuts, rtol=0, atol=0):
        raise ValueError('Cut decomposition differs')
    old = pd.read_csv(prior / 'diagnostics.csv')
    new = pd.read_csv(directory / 'diagnostic_trends.csv')
    new = new[new.length == new.groupby('state').length.transform('max')]
    count = 0
    for row in old[old.kind == 'distance'].itertuples():
        current = new[(new.state == row.state) & (new.cohort == row.cohort) & (new.metric == row.measure)].iloc[0]
        for field in ['rhat', 'bulk_ess', 'tail_ess']:
            if not np.isclose(current[field], getattr(row, field), rtol=1e-11, atol=1e-10):
                raise ValueError('Prior distance diagnostic differs')
        count += 1
    exports = ['README.md', 'figure_values.json', 'county_half_attribution.csv', 'final_reference_screens.csv',
               'county_window_changes.csv', 'successive_audit_changes.csv', 'resolution_summary.csv',
               'graph_count_decomposition.csv', 'mixing_traces.png', 'unit_resolution.png']
    for name in exports:
        if sha(directory / name) != sha(reproduced / name):
            raise ValueError('Report reproduction differs: ' + name)
    test_log = (directory / 'test_suite.log').read_text()
    match = re.search(r'Ran (\d+) tests', test_log)
    if not match or not test_log.rstrip().endswith('OK'):
        raise ValueError('Full test suite did not pass without skips')
    sources = ['paper/geographic_mixing.py', 'paper/geographic_mean_drivers.py', 'paper/geographic_unit_support.py',
               'paper/geographic_mixing_report.py', 'paper/check_geographic_mixing.py', 'tests/test_geographic_mixing.py']
    for name in sources:
        ast.parse(Path(name).read_text())
    unchanged = {}
    for name in ['src/chain/run_ensemble.py', 'src/chain/checkpoint_integrity.py']:
        if sha(name) != sha(root / name):
            raise ValueError('Sampler or checkpoint code differs')
        unchanged[name] = sha(name)
    receipt = {'tests_run': int(match[1]), 'test_failures': 0, 'test_skips': 0,
               'report_exports_byte_identical': len(exports), 'previous_distance_diagnostic_cases_reproduced': count,
               'all_retained_assignments_matched': len(scores), 'frozen_checksums': frozen,
               'unchanged_source_hashes': unchanged, 'analysis_source_hashes': {name: sha(name) for name in sources},
               'report_reproduction_scope': 'Copied score inputs using this runtime and repository county-half records; no clean-room raw-data rebuild or Linux execution.',
               'python_checks': 'AST parsing and unittest; no Python formatter or linter configured.',
               'verification_code_sha256': sha(__file__), 'research_ready': False}
    target.write_text(json.dumps(receipt, indent=2, allow_nan=False) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['source-root', 'review-dir', 'reproduced-dir', 'parallel-review']:
        parser.add_argument('--' + name, type=Path, required=True)
    a = parser.parse_args()
    check(a.source_root.resolve(), a.review_dir, a.reproduced_dir, a.parallel_review)
