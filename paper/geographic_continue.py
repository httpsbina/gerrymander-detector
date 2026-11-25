"""Continue every existing chain into a separate geographic campaign."""
import argparse
import copy
import fcntl
import json
import math
import os
from pathlib import Path
import pickle
import sys

import numpy as np
import pandas as pd

from paper.geographic_clustering import sha

GEOGRAPHIC = ('silhouette', 'normalized_rms_radius', 'mean_polsby_popper',
              'mean_distance_km', 'sd_distance_km', 'distance_cv', 'inverse_distance_cv', 'mean_district_cv',
              'internal_boundary_km', 'common_cut_edges', 'density_weighted_boundary',
              'area_normalized_rms_radius', 'area_weighted_polsby_popper', 'median_polsby_popper')


def passes(values, chains):
    if chains < 2:
        return False
    minimum = max(400, 100 * chains)
    return (set(values) == set(GEOGRAPHIC) and all(
        all(item[name]['status'] == 'finite' and item[name]['value'] is not None and math.isfinite(item[name]['value'])
            for name in ('rhat', 'bulk_ess', 'tail_ess', 'mcse_mean'))
        and item['rhat']['value'] < 1.01
        and item['bulk_ess']['value'] >= minimum and item['tail_ess']['value'] >= minimum
        for item in values.values()))


class Geography:
    def __init__(self, root, paper, cache):
        from paper.geographic_geometry import block_master
        from paper.geographic_refinement import sample_points
        from paper.compactness_mechanisms import polygon_moments
        import geopandas as gpd
        from scipy.spatial.distance import cdist
        self.root, self.cache, self.states = root, cache, {}
        a = pd.read_csv(paper / 'paper/reviews/parallel-comparison-20261118/paired_presidential.csv')
        b = pd.read_csv(paper / 'paper/reviews/compactness-mechanisms-20261109/scores.csv')
        keys = ['state', 'group', 'seed', 'step', 'plan_hash']
        a = a[~a.group.str.startswith('enacted')]
        b = b[~b.group.str.startswith('enacted')]
        self.table = a.merge(b[keys + [c for c in b if c not in a]], on=keys, how='outer', validate='one_to_one', indicator=True)
        if not (self.table._merge == 'both').all():
            raise ValueError('Historical geographic coverage differs')
        self.table = self.table.drop(columns='_merge')
        inventory = json.loads((cache / 'inventory.json').read_text())
        for state in ('nc', 'tx'):
            for name, expected in inventory['states'][state]['outputs'].items():
                if sha(cache / name) != expected:
                    raise ValueError('Changed measurement cache')
            master, _ = block_master(root, state)
            atoms = gpd.read_file(cache / f'{state}_atoms.gpkg', layer='atoms')
            point = np.load(cache / f'{state}_points.npz')
            if not np.array_equal(point['geoids'], master.GEOID20.to_numpy()):
                raise ValueError('Block order differs')
            sample_index, sample = sample_points(master, point['coordinates'], 20261109)
            lookup = dict(zip(atoms.atom, range(len(atoms))))
            block_atoms = np.array([lookup[x] for x in master.atom])
            edge = np.load(cache / f'{state}_edges.npz')
            left, right, length = edge['left'], edge['right'], edge['length']
            area, perimeter = atoms.geometry.area.to_numpy(), atoms.geometry.length.to_numpy()
            phi = (atoms.population.to_numpy()[left] + atoms.population.to_numpy()[right]) / (area[left] + area[right])
            self.states[state] = dict(atoms=atoms, population=master.TOTPOP.to_numpy(),
                points=point['coordinates'] - point['origin'], block_atoms=block_atoms,
                sample=sample, sample_atoms=block_atoms[sample_index], distance=cdist(sample, sample),
                area=area, perimeter=perimeter, edges=(left, right, length), weighted=length * np.sqrt(phi),
                moments=np.array([polygon_moments(g, point['origin']) for g in atoms.geometry]))
        self.node_maps = {}

    def update(self, key, e):
        from paper.parallel_analysis import radial_statistics
        from paper.geographic_refinement import moment_radius, boundary_scores
        from paper.geographic_clustering import scores
        from src.chain.benchmark_baselines import checkpoint_path
        import geopandas as gpd
        state = 'nc' if e['state'] == 'north_carolina' else 'tx'
        c = self.states[state]
        atoms = c['atoms']
        if key not in self.node_maps:
            frame = gpd.read_file(self.root / e['dataset'], layer='precincts', ignore_geometry=True)
            lookup = dict(zip(frame.UNIQUE_ID, range(len(frame))))
            self.node_maps[key] = np.array([lookup[u] for u in atoms.unit])
        new = []
        for seed in e['seeds']:
            prior = self.table[(self.table.group == key) & (self.table.seed == seed)]
            start = int(prior.step.max()) + 101
            trace = {}
            for path in (self.root / e['input_dir']).glob(f"{e['prefix']}_chain_*seed{seed}_steps*.csv"):
                frame = pd.read_csv(path, usecols=['step', 'plan_hash'])
                for row in frame.itertuples():
                    if int(row.step) in trace:
                        raise ValueError('Overlapping complete trace')
                    trace[int(row.step)] = row.plan_hash
            if set(trace) != set(range(e['steps'])):
                raise ValueError('Incomplete complete trace')
            for boundary in range(start, e['steps'] + 1, 100):
                path = checkpoint_path((self.root / e['input_dir']).parent / 'checkpoints', e, seed, boundary)
                with path.open('rb') as stream:
                    checkpoint = pickle.load(stream)
                if checkpoint['next_step'] != boundary or checkpoint['seed'] != seed or checkpoint['provenance'] != e['expected_checkpoint_provenance'][str(seed)]:
                    raise ValueError('Geographic checkpoint identity or provenance differs')
                if checkpoint['plan_hash'] != trace[boundary - 1]:
                    raise ValueError('Checkpoint and complete CSV differ')
                labels = np.array([checkpoint['assignment'][int(n)] for n in self.node_maps[key]], dtype=int)
                pp, district_area, _ = boundary_scores(c['area'], c['perimeter'], c['edges'], labels)
                radius, _ = moment_radius(*[atoms[x].to_numpy() for x in ['population', 'sx', 'sy', 'q']], labels)
                area_radius, _ = moment_radius(*c['moments'].T, labels)
                radial, _ = radial_statistics(c['points'], c['population'], labels[c['block_atoms']])
                left, right, length = c['edges'];cut = labels[left] != labels[right]
                row = dict(state=state, group=key, seed=seed, step=boundary - 1, plan_hash=checkpoint['plan_hash'],
                    silhouette=scores(c['sample'], labels[c['sample_atoms']], c['distance'])['silhouette'],
                    normalized_rms_radius=radius, mean_polsby_popper=float(pp.mean()),
                    internal_boundary_km=float(length[cut].sum() / 1000), common_cut_edges=int(cut.sum()),
                    density_weighted_boundary=float(c['weighted'][cut].sum()), area_normalized_rms_radius=area_radius,
                    area_weighted_polsby_popper=float(np.average(pp, weights=district_area)),
                    median_polsby_popper=float(np.median(pp)), **radial)
                new.append(row)
        if new:
            self.table = pd.concat([self.table, pd.DataFrame(new)], ignore_index=True)

    def audit(self, state, experiments, destination):
        import arviz as az
        from paper.review_precision import finite_call, half_comparison
        destination.mkdir(parents=True, exist_ok=False)
        for key, e in experiments.items():
            self.update(key, e)
        table = self.table[self.table.state == state]
        table.to_csv(destination / 'geographic_scores.csv', index=False)
        output, warmups, halves = {}, {}, {}
        for cohort in ['joint', *sorted(experiments)]:
            chosen = table if cohort == 'joint' else table[table.group == cohort]
            count = len(chosen.groupby(['group', 'seed']))
            for burn in (0, 250, 500, 1000):
                values = {}
                for metric in GEOGRAPHIC:
                    array = np.stack([chain.sort_values('step')[metric].to_numpy() for _, chain in chosen[chosen.step >= burn].groupby(['group', 'seed'])])
                    if not np.isfinite(array).all():
                        raise ValueError('Nonfinite geographic scores')
                    values[metric] = {name: finite_call(call) for name, call in {
                        'rhat': lambda: az.rhat(array, method='rank'), 'bulk_ess': lambda: az.ess(array, method='bulk'),
                        'tail_ess': lambda: az.ess(array, method='tail'), 'mcse_mean': lambda: az.mcse(array, method='mean'),
                        'mcse_sd': lambda: az.mcse(array, method='sd'), 'mcse_q05': lambda: az.mcse(array, method='quantile', prob=.05),
                        'mcse_q95': lambda: az.mcse(array, method='quantile', prob=.95)}.items()}
                    if burn == 500:
                        halves[cohort + ':' + metric] = half_comparison(array)
                warmups[cohort + ':' + str(burn)] = values
                if burn == 500:
                    output[cohort] = dict(chains=count, ess_minimum=max(400, 100 * count), metrics=values, passes=passes(values, count))
        finite = all(v['status'] == 'finite' for values in warmups.values() for metric in values.values() for v in metric.values())
        retained = table[table.step >= 500].copy()
        retained['window_start'] = retained.step.astype(int) // 5000 * 5000
        retained.groupby(['group', 'seed', 'window_start'])[list(GEOGRAPHIC)].agg(['mean', 'std', 'count']).to_csv(destination / 'window_stability.csv')
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig, axes = plt.subplots(7, 2, figsize=(14, 20), constrained_layout=True)
        for ax, metric in zip(axes.flat, GEOGRAPHIC):
            for (group, seed), chunk in retained.groupby(['group', 'seed']):
                chunk = chunk.sort_values('step')
                ax.plot(chunk.step, chunk[metric], linewidth=.4, alpha=.6, label=f'{group}:{int(seed)}')
            ax.set(title=metric, xlabel='Recorded step')
        axes.flat[0].legend(fontsize=6, ncol=2)
        fig.savefig(destination / 'geographic_traces.png', dpi=120)
        plt.close(fig)
        report = dict(state=state, steps={key: e['steps'] for key, e in experiments.items()}, cohorts=output,
                      warmup_sensitivity=warmups, half_history=halves, all_diagnostics_finite=finite,
                      geographic_screens_pass=finite and all(c['passes'] for c in output.values()), research_ready=False)
        (destination / 'geographic_diagnostics.json').write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
        return report


def execute(root, paper, manifest_path, cache, destination):
    sys.path.insert(0, str(root))
    from src.chain.continue_baselines import run_wave, ROOT
    from src.chain.run_texas_until_freeze import audit_milestone
    if ROOT != root:
        raise ValueError('Continuation helper loaded from wrong checkout')
    manifest = json.loads(manifest_path.read_text())
    destination.mkdir(parents=True, exist_ok=False)
    lock = (destination / 'controller.lock').open('x')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    status = {'pid': os.getpid(), 'states': {}, 'complete': False}
    (destination / 'rules.json').write_text(json.dumps(dict(metrics=GEOGRAPHIC, rhat_below=1.01,
        ess_minimum='max(400,100*chains)', warmup=500, checkpoint_interval=100, audit_interval=5000,
        workers=8, controller_sha256=sha(__file__), frozen_results_changed=False), indent=2) + '\n')
    geography = None
    passed = {'nc': False, 'tx': False}
    experiments = manifest['experiments']
    lengths = {(k, seed): e['steps'] for k, e in experiments.items() for seed in e['seeds']}
    status['states'] = {state: {'steps': next(e['steps'] for e in experiments.values() if (e['state'] == 'north_carolina') == (state == 'nc')), 'geographic_screens_pass': False} for state in ['nc', 'tx']}
    (destination / 'status.json').write_text(json.dumps(status, indent=2) + '\n')
    previous = {state: json.loads((manifest_path.parent / 'scoring_validation' / state / 'geographic_diagnostics.json').read_text()) for state in ['nc', 'tx']}
    wave = 0
    while not all(passed.values()):
        wave += 1
        jobs = []
        for key, e in sorted(experiments.items(), key=lambda item: item[1]['state'] != 'north_carolina'):
            state = 'nc' if e['state'] == 'north_carolina' else 'tx'
            if not passed[state]:
                count = min(1000, (e['steps'] // 5000 + 1) * 5000 - e['steps'])
                jobs.extend((key, seed, count) for seed in e['seeds'])
        run_wave(manifest, jobs, lengths, destination / f'wave_{wave:06d}', 8)
        for key, e in experiments.items():
            e['steps'] = lengths[(key, e['seeds'][0])]
        path = destination / f'manifest_{wave:06d}.json'
        path.write_text(json.dumps(manifest, indent=2) + '\n')
        audited = False
        for state in ('nc', 'tx'):
            subset = {k: e for k, e in experiments.items() if (e['state'] == 'north_carolina') == (state == 'nc')}
            step = next(iter(subset.values()))['steps']
            status['states'][state] = {'steps': step, 'geographic_screens_pass': passed[state]}
            if passed[state] or step % 5000:
                continue
            audited = True
            audit_dir = destination / f'{state}_{step:06d}'
            audit_dir.mkdir()
            audit_milestone(dict(source_code=manifest['source_code'], experiments=subset), audit_dir / 'primary')
            if geography is None:
                geography = Geography(root, paper, cache)
            report = geography.audit(state, subset, audit_dir / 'geography')
            primary = json.loads((audit_dir / 'primary/audit/diagnostics.json').read_text())
            entries = list(primary['experiments'].values())
            entries.append(primary['joint_nc']['nc_block_union'] if state == 'nc' else primary['joint_texas'])
            primary_pass = all(entry['diagnostics'] and all(v['all_finite'] and not v['screening_flags'] for v in entry['diagnostics'].values()) for entry in entries)
            regressions = []
            for cohort, entry in report['cohorts'].items():
                for metric, values in entry['metrics'].items():
                    old = previous[state]['cohorts'][cohort]['metrics'][metric]
                    for field in ['bulk_ess', 'tail_ess']:
                        if values[field]['value'] is None or old[field]['value'] is None or values[field]['value'] <= old[field]['value']:
                            regressions.append(dict(cohort=cohort, metric=metric, diagnostic=field, previous=old[field]['value'], current=values[field]['value']))
            (audit_dir / 'ess_changes.json').write_text(json.dumps(regressions, indent=2, allow_nan=False) + '\n')
            previous[state] = report
            print(json.dumps({'state': state, 'steps': step, 'geographic_metrics': report['cohorts'], 'flat_or_decreasing_ess': regressions}), flush=True)
            passed[state] = bool(report['geographic_screens_pass'] and primary_pass)
            status['states'][state] = {'steps': step, 'geographic_screens_pass': passed[state], 'audit': str(audit_dir.relative_to(root))}
            print(json.dumps(status), flush=True)
        if audited:
            from paper.geographic_backup import backup
            try:
                status['backup'] = backup(root, paper, manifest_path.parent, path, root / 'outputs/analysis/geographic_backups_20261118' / f'wave_{wave:06d}')
            except Exception as exc:
                status['backup'] = {'status': 'failed', 'error': f'{type(exc).__name__}: {exc}'}
                print(json.dumps({'backup_failure': status['backup']}), flush=True)
        status['complete'] = all(passed.values())
        (destination / 'status.json').write_text(json.dumps(status, indent=2) + '\n')
    print('Both states pass the recorded geographic and primary numerical screens; frozen results remain unchanged.', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['source-root', 'manifest', 'measurement-cache', 'output-dir']:
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--validate-scoring-only', action='store_true')
    a = parser.parse_args()
    if a.validate_scoring_only:
        root = a.source_root.resolve()
        sys.path.insert(0, str(root))
        from src.chain.continue_baselines import ROOT
        if ROOT != root:
            raise ValueError('Scoring helper loaded from wrong checkout')
        manifest = json.loads(a.manifest.read_text())
        geo = Geography(root, Path(__file__).resolve().parents[1], a.measurement_cache)
        checked = 0
        for key, e in manifest['experiments'].items():
            before = geo.table[(geo.table.group == key) & (geo.table.step == e['steps'] - 1)].copy()
            geo.table = geo.table[~((geo.table.group == key) & (geo.table.step == e['steps'] - 1))]
            geo.update(key, e)
            after = geo.table[(geo.table.group == key) & (geo.table.step == e['steps'] - 1)]
            for seed in e['seeds']:
                x = before[before.seed == seed].iloc[0]
                y = after[after.seed == seed].iloc[0]
                if x.plan_hash != y.plan_hash or not np.allclose(x[list(GEOGRAPHIC)].to_numpy(dtype=float), y[list(GEOGRAPHIC)].to_numpy(dtype=float), rtol=1e-10, atol=1e-10):
                    raise ValueError('Continued geographic scorer differs from frozen measurements')
                checked += len(GEOGRAPHIC)
        a.output_dir.mkdir(parents=True, exist_ok=False)
        for state in ['nc', 'tx']:
            subset = {k: e for k, e in manifest['experiments'].items() if (e['state'] == 'north_carolina') == (state == 'nc')}
            geo.audit(state, subset, a.output_dir / state)
        (a.output_dir / 'verification.json').write_text(json.dumps(dict(score_cells_reproduced=checked, assignments=14, code_sha256=sha(__file__)), indent=2) + '\n')
    else:
        execute(a.source_root.resolve(), Path(__file__).resolve().parents[1], a.manifest, a.measurement_cache, a.output_dir.resolve())
