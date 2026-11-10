"""Compare geographic clustering on fixed population-sampled Census block locations."""

import argparse
import hashlib
import json
import pickle
from pathlib import Path
from zipfile import ZipFile

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.spatial.distance import cdist
from scipy.stats import spearmanr

CAMPAIGN = Path('outputs/analysis/convergence_campaign_2026-11-02')
METRICS = ('silhouette', 'normalized_rms_radius', 'radial_cv')


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def scores(points, labels, distances=None):
    """Exact scores for the supplied empirical population sample, including duplicates."""
    points, labels = np.asarray(points), np.asarray(labels)
    groups = np.unique(labels)
    if len(groups) < 2 or not np.isfinite(points).all():
        raise ValueError('Invalid geographic sample')
    distances = cdist(points, points) if distances is None else distances
    means = np.column_stack([distances[:, labels == group].mean(axis=1) for group in groups])
    within, radius, cv, weights = [], [], [], []
    for column, group in enumerate(groups):
        mask = labels == group
        count = int(mask.sum())
        if count < 2:
            raise ValueError('A sampled district has fewer than two observations')
        a = means[mask, column] * count / (count - 1)
        b = np.delete(means[mask], column, axis=1).min(axis=1)
        denominator = np.maximum(a, b)
        within.extend(np.divide(b - a, denominator, out=np.zeros_like(a), where=denominator > 0))
        x = points[mask]
        r = np.linalg.norm(x - x.mean(axis=0), axis=1)
        if r.mean() == 0:
            raise ValueError('Undefined radial coefficient of variation')
        radius.append(np.mean(r ** 2))
        cv.append(r.std(ddof=0) / r.mean())
        weights.append(count)
    statewide_rms = np.sqrt(np.mean(np.sum((points - points.mean(axis=0)) ** 2, axis=1)))
    return dict(zip(METRICS, [float(np.mean(within)),
        float(np.sqrt(np.average(radius, weights=weights)) / statewide_rms),
        float(np.average(cv, weights=weights))]))


def run(root, output):
    if output.exists():
        raise FileExistsError(output)
    output.mkdir(parents=True)
    records, rows, inventories = {}, [], {}
    manifests = {
        'tx': CAMPAIGN / 'tx_shared45000_continuation_20261103/shared_070000/manifest.json',
        'nc': CAMPAIGN / 'nc_primary_continuation/snapshot_003/manifest.json',
    }
    for state, manifest in manifests.items():
        path = root / manifest
        records[str(manifest)] = sha(path)
        experiments = json.loads(path.read_text())['experiments']
        master_path = root / f'outputs/analysis/rdh_rebuild_2026-11-02/{state}_block_audit/blocks_master.csv'
        records[str(master_path.relative_to(root))] = sha(master_path)
        master = pd.read_csv(master_path, dtype={'GEOID20': str, 'PRECINCTID': str})
        if not master.GEOID20.is_unique or (master.TOTPOP < 0).any():
            raise ValueError('Invalid block master')
        if state == 'tx':
            master['unit'] = master.PRECINCTID
        else:
            precinct = master.PRECINCTID.replace({'WAKE-:-01-07 & WAKE-:-01-07A': 'WAKE-:-01-07'})
            master['unit'] = precinct + '|' + master.DISTRICT_2023.astype(str).str.zfill(2)
            split = master.groupby('unit').DISTRICT_2025.transform('nunique') > 1
            master.loc[split, 'unit'] += '|25-' + master.loc[split, 'DISTRICT_2025'].astype(str).str.zfill(2)
        rng = np.random.default_rng(20261109)
        index = rng.choice(len(master), 2048, replace=True, p=master.TOTPOP.to_numpy() / master.TOTPOP.sum())
        sample = master.iloc[index].copy()
        state_name = 'texas' if state == 'tx' else 'north_carolina'
        archive = root / f'data/external/rdh/rebuild_2026-11-02/{state_name}/{state}_pl2020_b.zip'
        records[str(archive.relative_to(root))] = sha(archive)
        member = next(name for name in ZipFile(archive).namelist() if name.endswith('.shp'))
        ids = sorted(set(sample.GEOID20))
        where = 'GEOID20 IN (' + ','.join("'" + value + "'" for value in ids) + ')'
        blocks = gpd.read_file(f'/vsizip/{archive}/{member}', columns=['GEOID20'], where=where).to_crs(5070)
        if not blocks.GEOID20.is_unique or set(blocks.GEOID20) != set(ids):
            raise ValueError('Sampled block geometry coverage differs')
        if not blocks.geometry.is_valid.all() or blocks.geometry.is_empty.any():
            raise ValueError('Invalid sampled block geometry')
        centroids = blocks.set_index('GEOID20').geometry.centroid.loc[sample.GEOID20]
        points = np.column_stack([centroids.x, centroids.y])
        distances = cdist(points, points)
        pd.DataFrame({'GEOID20': sample.GEOID20.to_numpy(), 'x_m': points[:, 0], 'y_m': points[:, 1]}).to_csv(output / f'{state}_sample.csv', index=False)
        inventories[state] = {'population': int(master.TOTPOP.sum()), 'blocks': len(master), 'zero_population_blocks_preserved_in_master': int((master.TOTPOP == 0).sum()), 'unique_sampled_blocks': len(ids)}
        for year in ([2025] if state == 'tx' else [2023, 2025]):
            labels = sample[f'DISTRICT_{year}'].to_numpy()
            for n in (1024, 2048):
                if len(np.unique(labels[:n])) != (38 if state == 'tx' else 14):
                    raise ValueError('Missing sampled enacted district')
                rows.append({'state': state, 'group': f'enacted_{year}', 'seed': None, 'step': None, 'sample_size': n, **scores(points[:n], labels[:n], distances[:n, :n])})
        for group, spec in experiments.items():
            dataset = root / spec['dataset']
            if sha(dataset) != spec['dataset_sha256']:
                raise ValueError('Dataset identity differs')
            records[spec['dataset']] = sha(dataset)
            frame = gpd.read_file(dataset, layer='precincts', ignore_geometry=True)
            if not frame.UNIQUE_ID.is_unique or set(frame.UNIQUE_ID) != set(master.unit):
                raise ValueError('Unit coverage differs')
            lookup = dict(zip(frame.UNIQUE_ID, range(len(frame))))
            nodes = np.array([lookup[value] for value in sample.unit])
            tag = f"{spec['epsilon']:g}".replace('.', 'p')
            boundaries = np.round(np.linspace(1000, spec['steps'], 10) / 100).astype(int) * 100
            directories = [root / CAMPAIGN / group / 'checkpoints', root / 'outputs/analysis/rebuild_campaign_2026-11-02' / group / 'checkpoints']
            if group == 'tx_dispersed':
                directories = [root / CAMPAIGN / 'texas_independent_dispersed/checkpoints']
            for seed in spec['seeds']:
                for boundary in boundaries:
                    name = f"{spec['prefix']}_checkpoint_eps{tag}_seed{seed}_next{boundary}.pkl"
                    paths = [directory / name for directory in directories if (directory / name).is_file()]
                    if not paths or len({sha(path) for path in paths}) != 1:
                        raise ValueError(f'Missing or conflicting checkpoint {name}')
                    path = paths[0]
                    records[str(path.relative_to(root))] = sha(path)
                    with path.open('rb') as stream:
                        checkpoint = pickle.load(stream)
                    if checkpoint['seed'] != seed or checkpoint['next_step'] != boundary or checkpoint['provenance']['dataset_sha256'] != spec['dataset_sha256']:
                        raise ValueError('Checkpoint identity differs')
                    if set(checkpoint['assignment']) != set(range(len(frame))):
                        raise ValueError('Checkpoint assignment coverage differs')
                    labels = np.array([checkpoint['assignment'][int(node)] for node in nodes])
                    if len(np.unique(labels)) != spec['districts']:
                        raise ValueError('Missing sampled simulation district')
                    for n in (1024, 2048):
                        if len(np.unique(labels[:n])) != spec['districts']:
                            raise ValueError('Missing sampled simulation district')
                        rows.append({'state': state, 'group': group, 'seed': seed, 'step': int(boundary - 1), 'sample_size': n, **scores(points[:n], labels[:n], distances[:n, :n])})
                print(state, group, seed, 'complete', flush=True)
    table = pd.DataFrame(rows)
    table.to_csv(output / 'scores.csv', index=False)
    comparisons, correlations = [], []
    for (state, n), subset in table.groupby(['state', 'sample_size']):
        simulated = subset[~subset.group.str.startswith('enacted')]
        for group in ['joint', *sorted(simulated.group.unique())]:
            values = simulated if group == 'joint' else simulated[simulated.group == group]
            for enacted in subset[subset.group.str.startswith('enacted')].to_dict('records'):
                for metric in METRICS:
                    x = values[metric].to_numpy()
                    comparisons.append({'state': state, 'sample_size': int(n), 'cohort': group, 'enacted': enacted['group'], 'metric': metric, 'value': enacted[metric], 'sampled_plans': len(x), 'median': float(np.median(x)), 'minimum': float(x.min()), 'maximum': float(x.max()), 'fraction_at_or_below': float(np.mean(x <= enacted[metric]))})
        for i, a in enumerate(METRICS):
            for b in METRICS[i + 1:]:
                correlations.append({'state': state, 'sample_size': int(n), 'first': a, 'second': b, 'spearman': float(spearmanr(simulated[a], simulated[b]).statistic)})
    pd.DataFrame(comparisons).to_csv(output / 'comparisons.csv', index=False)
    result = {'seed': 20261109, 'crs': 'EPSG:5070', 'method': 'Population-proportional block sampling with replacement; block centroids; nested sample sizes; ten equally spaced available post-warmup checkpoint boundaries per chain, including its terminal boundary. Exact silhouette on each empirical sample, not exact statewide silhouette.', 'freeze_check': False, 'inventory': inventories, 'comparisons': comparisons, 'correlations': correlations, 'input_checksums': records, 'code_sha256': sha(__file__)}
    (output / 'results.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    run(args.source_root.resolve(), args.output_dir)


if __name__ == '__main__':
    main()
