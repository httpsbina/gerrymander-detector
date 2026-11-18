"""Check radial distance sensitivity to ellipsoidal distances at fixed population centers."""

import argparse
import json
from pathlib import Path
import pickle

import geopandas as gpd
import numpy as np
import pandas as pd
from pyproj import Geod, Transformer

from paper.frozen_elections import MANIFESTS
from paper.geographic_clustering import CAMPAIGN, sha
from paper.geographic_geometry import block_master


def run(root, cache, directory):
    target = directory / 'projection_sensitivity.json'
    if target.exists():
        raise FileExistsError(target)
    source = json.loads((directory / 'results.json').read_text())
    table = pd.read_csv(directory / 'paired_presidential.csv')
    rows = []
    transformer, geod = Transformer.from_crs(5070, 4269, always_xy=True), Geod(ellps='GRS80')
    for state in ('tx', 'nc'):
        master, _ = block_master(root, state)
        data = np.load(cache / f'{state}_points.npz')
        if not np.array_equal(data['geoids'], master.GEOID20.to_numpy()):
            raise ValueError('Block coordinates differ')
        points, population = data['coordinates'], master.TOTPOP.to_numpy(dtype=float)
        longitude, latitude = transformer.transform(points[:, 0], points[:, 1])
        atoms = gpd.read_file(cache / f'{state}_atoms.gpkg', layer='atoms', ignore_geometry=True)
        lookup = dict(zip(atoms.atom, range(len(atoms))))
        block_atoms = np.array([lookup[value] for value in master.atom])
        specs = json.loads((root / MANIFESTS[state]).read_text())['experiments']
        node_maps = {}
        for group, spec in specs.items():
            units = gpd.read_file(root / spec['dataset'], layer='precincts', ignore_geometry=True).UNIQUE_ID
            mapping = dict(zip(units, range(len(units))))
            node_maps[group] = np.array([mapping[value] for value in atoms.unit])
        for row in table[table.state == state].to_dict('records'):
            if row['group'].startswith('enacted'):
                labels = atoms['enacted_' + row['group'].split('_')[-1]].to_numpy(dtype=int)[block_atoms]
            else:
                group, spec = row['group'], specs[row['group']]
                boundary, seed = int(row['step']) + 1, int(row['seed'])
                pilot = set(np.round(np.linspace(1000, spec['steps'], 10) / 100).astype(int) * 100)
                if boundary not in pilot:
                    continue
                tag = f"{spec['epsilon']:g}".replace('.', 'p')
                name = f"{spec['prefix']}_checkpoint_eps{tag}_seed{seed}_next{boundary}.pkl"
                folders = [root / CAMPAIGN / group / 'checkpoints', root / 'outputs/analysis/rebuild_campaign_2026-11-02' / group / 'checkpoints']
                if group == 'tx_dispersed':
                    folders = [root / CAMPAIGN / 'texas_independent_dispersed/checkpoints']
                path = next((folder / name for folder in folders if (folder / name).is_file()), None)
                if path is None or sha(path) != source['input_checksums'].get(str(path.relative_to(root))):
                    raise ValueError('Missing or changed projection checkpoint')
                with path.open('rb') as stream:
                    checkpoint = pickle.load(stream)
                if checkpoint['plan_hash'] != row['plan_hash']:
                    raise ValueError('Projection plan differs')
                atom_labels = np.array([checkpoint['assignment'][int(node)] for node in node_maps[group]], dtype=int)
                labels = atom_labels[block_atoms]
            mass = np.bincount(labels, weights=population)
            centers = np.column_stack([np.divide(np.bincount(labels, weights=population * points[:, axis]), mass, out=np.zeros_like(mass), where=mass > 0) for axis in (0, 1)])
            center_lon, center_lat = transformer.transform(centers[:, 0], centers[:, 1])
            _, _, distance = geod.inv(longitude, latitude, center_lon[labels], center_lat[labels])
            mean = float(np.average(distance, weights=population) / 1000)
            sd = float(np.sqrt(np.average((distance / 1000 - mean) ** 2, weights=population)))
            result = {key: row[key] for key in ['state', 'group', 'seed', 'step']}
            result.update({'projected_mean_km': row['mean_distance_km'], 'ellipsoidal_mean_km': mean, 'projected_sd_km': row['sd_distance_km'], 'ellipsoidal_sd_km': sd, 'projected_cv': row['distance_cv'], 'ellipsoidal_cv': sd / mean})
            rows.append(result)
        print(state, 'projection checks complete', flush=True)
    output = pd.DataFrame(rows)
    output.to_csv(directory / 'projection_sensitivity.csv', index=False)
    changes = {metric: float(np.max(np.abs(output[f'ellipsoidal_{metric}'] / output[f'projected_{metric}'] - 1))) for metric in ['mean_km', 'sd_km', 'cv']}
    target.write_text(json.dumps({'method': 'All Census-block locations on the previously defined ten-checkpoint-per-chain pilot and each enacted map. GRS80 ellipsoidal distances go to the same EPSG:5070 population-center locations; centers are not re-optimized on the ellipsoid. This tests distance projection sensitivity, not every possible center definition.', 'assignments_checked': len(rows), 'maximum_absolute_relative_changes': changes, 'research_ready': False}, indent=2, allow_nan=False) + '\n')
    print(json.dumps(changes))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--measurement-cache', type=Path, required=True)
    parser.add_argument('--review-dir', type=Path, required=True)
    args = parser.parse_args()
    run(args.source_root.resolve(), args.measurement_cache, args.review_dir)


if __name__ == '__main__':
    main()
