"""Build a common block-derived geometry for geographic measurement only."""

import argparse
import json
from pathlib import Path
from zipfile import ZipFile

import geopandas as gpd
import numpy as np
import pandas as pd
import pyogrio
import shapely

from paper.geographic_clustering import sha


def block_master(root, state):
    path = root / f'outputs/analysis/rdh_rebuild_2026-11-02/{state}_block_audit/blocks_master.csv'
    columns = ['GEOID20', 'PRECINCTID', 'TOTPOP', 'DISTRICT_2025']
    if state == 'nc':
        columns.append('DISTRICT_2023')
    frame = pd.read_csv(path, usecols=columns, dtype={'GEOID20': str, 'PRECINCTID': str})
    if not frame.GEOID20.is_unique or frame.isna().any().any() or (frame.TOTPOP < 0).any():
        raise ValueError('Invalid block master')
    if state == 'tx':
        frame['unit'] = frame.PRECINCTID
    else:
        precinct = frame.PRECINCTID.replace({'WAKE-:-01-07 & WAKE-:-01-07A': 'WAKE-:-01-07'})
        frame['unit'] = precinct + '|' + frame.DISTRICT_2023.astype(str).str.zfill(2)
        split = frame.groupby('unit').DISTRICT_2025.transform('nunique') > 1
        frame.loc[split, 'unit'] += '|25-' + frame.loc[split, 'DISTRICT_2025'].astype(str).str.zfill(2)
    frame['atom'] = frame.unit + '|enacted25-' + frame.DISTRICT_2025.astype(str)
    return frame, path


def partition_edges(geometries):
    """Shared boundary lengths on a disjoint polygon partition; overlaps fail closed."""
    geometries = np.asarray(geometries, dtype=object)
    pairs = shapely.STRtree(geometries).query(geometries, predicate='intersects')
    left, right = pairs[:, pairs[0] < pairs[1]]
    shared = shapely.intersection(geometries[left], geometries[right])
    overlaps = shapely.area(shared)
    if (overlaps > 0).any():
        raise ValueError(f'Positive-area overlaps in measurement partition: {int((overlaps > 0).sum())}; maximum {float(overlaps.max())} m2')
    lengths = shapely.length(shared)
    return left[lengths > 0], right[lengths > 0], lengths[lengths > 0]


def build(root, output, chunk_size=50000):
    if output.exists():
        raise FileExistsError(output)
    output.mkdir(parents=True)
    inventory = {'crs': 'EPSG:5070', 'purpose': 'Geographic measurement only; original simulation geography and adjacency unchanged', 'states': {}}
    for state, state_name in [('tx', 'texas'), ('nc', 'north_carolina')]:
        master, master_path = block_master(root, state)
        index = pd.Index(master.GEOID20)
        archive = root / f'data/external/rdh/rebuild_2026-11-02/{state_name}/{state}_pl2020_b.zip'
        member = next(name for name in ZipFile(archive).namelist() if name.endswith('.shp'))
        uri = f'/vsizip/{archive}/{member}'
        count = pyogrio.read_info(uri)['features']
        if count != len(master):
            raise ValueError('Block geometry and master counts differ')
        coordinates = np.full((count, 2), np.nan)
        seen = np.zeros(count, dtype=bool)
        pieces = {}
        for first in range(0, count, chunk_size):
            frame = gpd.read_file(uri, columns=['GEOID20'], skip_features=first, max_features=chunk_size).to_crs(5070)
            nodes = index.get_indexer(frame.GEOID20)
            if (nodes < 0).any() or len(set(nodes)) != len(nodes) or seen[nodes].any():
                raise ValueError('Missing or duplicate block identity')
            if not frame.geometry.is_valid.all() or frame.geometry.is_empty.any() or frame.geometry.isna().any():
                raise ValueError('Invalid block geometry; no repair applied')
            centroid = frame.geometry.centroid
            coordinates[nodes] = np.column_stack([centroid.x, centroid.y])
            seen[nodes] = True
            frame['atom'] = master.atom.to_numpy()[nodes]
            for atom, group in frame.groupby('atom', sort=False):
                pieces.setdefault(atom, []).append(shapely.union_all(group.geometry.to_numpy()))
            print(state, 'blocks', int(seen.sum()), '/', count, flush=True)
        if not seen.all() or not np.isfinite(coordinates).all():
            raise ValueError('Incomplete coordinate coverage')
        atoms = master.groupby('atom', sort=True).agg(unit=('unit', 'first'), population=('TOTPOP', 'sum'), enacted_2025=('DISTRICT_2025', 'first'))
        if state == 'nc':
            atoms['enacted_2023'] = master.groupby('atom').DISTRICT_2023.first()
        geometry = [shapely.union_all(pieces[atom]) for atom in atoms.index]
        frame = gpd.GeoDataFrame(atoms.reset_index(), geometry=geometry, crs=5070)
        if not frame.geometry.is_valid.all() or frame.geometry.is_empty.any():
            raise ValueError('Invalid atom geometry')
        left, right, length = partition_edges(frame.geometry.to_numpy())
        origin = np.average(coordinates, weights=master.TOTPOP, axis=0)
        centered = coordinates - origin
        moments = pd.DataFrame({'atom': master.atom, 'sx': master.TOTPOP * centered[:, 0], 'sy': master.TOTPOP * centered[:, 1], 'q': master.TOTPOP * np.sum(centered ** 2, axis=1)}).groupby('atom').sum().loc[frame.atom]
        frame['sx'], frame['sy'], frame['q'] = moments.sx.to_numpy(), moments.sy.to_numpy(), moments.q.to_numpy()
        frame.to_file(output / f'{state}_atoms.gpkg', layer='atoms', driver='GPKG', index=False)
        np.savez_compressed(output / f'{state}_points.npz', coordinates=coordinates, origin=origin, geoids=master.GEOID20.to_numpy(dtype=str))
        np.savez_compressed(output / f'{state}_edges.npz', left=left, right=right, length=length)
        inventory['states'][state] = {'blocks': count, 'zero_population_blocks': int((master.TOTPOP == 0).sum()), 'population': int(master.TOTPOP.sum()), 'simulation_units': int(master.unit.nunique()), 'measurement_atoms': len(frame), 'positive_shared_boundaries': len(left), 'positive_area_overlap_pairs': 0, 'inputs': {str(master_path.relative_to(root)): sha(master_path), str(archive.relative_to(root)): sha(archive)}, 'outputs': {name: sha(output / name) for name in [f'{state}_atoms.gpkg', f'{state}_points.npz', f'{state}_edges.npz']}}
        (output / 'progress.json').write_text(json.dumps(inventory, indent=2) + '\n')
        print(state, 'measurement partition complete', flush=True)
    inventory['code_sha256'] = sha(__file__)
    (output / 'inventory.json').write_text(json.dumps(inventory, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    build(args.source_root.resolve(), args.output_dir)


if __name__ == '__main__':
    main()
