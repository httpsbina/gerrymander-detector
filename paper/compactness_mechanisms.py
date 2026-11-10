"""Examine boundary and population weighting on existing frozen assignments."""

import argparse
import csv
from importlib import metadata
import json
from pathlib import Path
import pickle
from zipfile import ZipFile

import arviz as az
import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

from paper.geographic_clustering import CAMPAIGN, sha
from paper.geographic_geometry import block_master
from paper.geographic_refinement import boundary_scores, moment_radius
from paper.review_precision import finite_call, half_comparison

METRICS = ('internal_boundary_km', 'common_cut_edges', 'density_weighted_boundary',
           'area_normalized_rms_radius', 'area_weighted_polsby_popper', 'median_polsby_popper')
SOURCES = ['https://arxiv.org/html/2501.02325', 'https://arxiv.org/html/1803.02857']


def polygon_moments(geometry, origin):
    """Integrate area, x, y and squared radius, preserving holes and components."""
    if geometry.is_empty or not geometry.is_valid:
        raise ValueError('Valid nonempty geometry required')
    answer = np.zeros(4)
    for polygon in shapely.get_parts(geometry):
        if polygon.geom_type != 'Polygon':
            raise ValueError('Polygon geometry required')
        for ring, role in [(polygon.exterior, 1), *[(item, -1) for item in polygon.interiors]]:
            absolute = np.asarray(ring.coords)
            anchor = absolute[0]
            local = absolute - anchor
            x, y = local[:-1, 0], local[:-1, 1]
            xx, yy = local[1:, 0], local[1:, 1]
            cross = x * yy - xx * y
            area = cross.sum() / 2
            if area == 0:
                raise ValueError('Degenerate polygon ring')
            sx, sy = np.sum((x + xx) * cross) / 6, np.sum((y + yy) * cross) / 6
            q = np.sum((x * x + x * xx + xx * xx + y * y + y * yy + yy * yy) * cross) / 12
            dx, dy = anchor - origin
            answer += role * np.sign(area) * np.array([area, sx + dx * area, sy + dy * area,
                q + 2 * dx * sx + 2 * dy * sy + (dx * dx + dy * dy) * area])
    if answer[0] <= 0 or not np.isfinite(answer).all():
        raise ValueError('Invalid polygon moments')
    return answer


def county_contributions(population, sx, sy, q, county_index, atom_index, atom_labels, atoms):
    """Additive county contributions to squared normalized population radius."""
    labels = atom_labels[atom_index]
    district_population = np.bincount(atom_labels, weights=atoms.population.to_numpy())
    center_x = np.bincount(atom_labels, weights=atoms.sx.to_numpy()) / np.where(district_population > 0, district_population, 1)
    center_y = np.bincount(atom_labels, weights=atoms.sy.to_numpy()) / np.where(district_population > 0, district_population, 1)
    local = q - 2 * center_x[labels] * sx - 2 * center_y[labels] * sy + population * (center_x[labels] ** 2 + center_y[labels] ** 2)
    if (local < -1e-5).any():
        raise ValueError('Negative county squared distance')
    total = atoms.q.sum() - (atoms.sx.sum() ** 2 + atoms.sy.sum() ** 2) / atoms.population.sum()
    return np.bincount(county_index, weights=local) / total


def load_county_moments(root, state, master, points, origin, atoms, records):
    centered = points - origin
    frame = pd.DataFrame({'county': master.GEOID20.str[:5], 'atom': master.atom, 'population': master.TOTPOP,
        'sx': master.TOTPOP * centered[:, 0], 'sy': master.TOTPOP * centered[:, 1],
        'q': master.TOTPOP * np.sum(centered ** 2, axis=1)})
    grouped = frame.groupby(['county', 'atom'], sort=True).sum().reset_index()
    county_ids = sorted(frame.county.unique())
    atom_lookup = dict(zip(atoms.atom, range(len(atoms))))
    atom_index = np.array([atom_lookup[value] for value in grouped.atom])
    county_lookup = {value: index for index, value in enumerate(county_ids)}
    county_index = np.array([county_lookup[value] for value in grouped.county])
    if state == 'tx':
        archive = root / 'data/external/rdh/rebuild_2026-11-02/texas/tx_2024_gen_tx_vtd.zip'
        member = next(name for name in ZipFile(archive).namelist() if name.endswith('.shp'))
        names = gpd.read_file(f'/vsizip/{archive}/{member}', columns=['COUNTYFP', 'County'], ignore_geometry=True)
        names['county'] = '48' + names.COUNTYFP.astype(int).astype(str).str.zfill(3)
        if names.groupby('county').County.nunique().max() != 1:
            raise ValueError('Ambiguous county name')
        mapping = names.groupby('county').County.first().to_dict()
        records[str(archive.relative_to(root))] = sha(archive)
    else:
        names = pd.DataFrame({'county': master.GEOID20.str[:5], 'name': master.PRECINCTID.str.split('-:-').str[0]})
        if names.groupby('county').name.nunique().max() != 1:
            raise ValueError('Ambiguous county name')
        mapping = names.groupby('county').name.first().to_dict()
    if not set(county_ids) <= set(mapping):
        raise ValueError('Missing county name')
    return grouped, county_ids, mapping, atom_index, county_index


def run(root, cache, geographic_review, output):
    if output.exists():
        raise FileExistsError(output)
    output.mkdir(parents=True)
    prior = json.loads((geographic_review / 'results.json').read_text())
    inventory = prior['measurement_inventory']
    prior_scores = pd.read_csv(geographic_review / 'scores.csv')
    records = dict(prior['input_checksums'])
    for relative, expected in records.items():
        if sha(root / relative) != expected:
            raise ValueError(f'Changed research input: {relative}')
    rows, boundaries, county_means, county_halves, checks = [], [], [], [], []
    for state in ('tx', 'nc'):
        for name, expected in inventory['states'][state]['outputs'].items():
            if sha(cache / name) != expected:
                raise ValueError('Changed measurement cache')
        atoms = gpd.read_file(cache / f'{state}_atoms.gpkg', layer='atoms')
        edge_file = np.load(cache / f'{state}_edges.npz')
        left, right, length = edge_file['left'], edge_file['right'], edge_file['length']
        point_file = np.load(cache / f'{state}_points.npz')
        master, _ = block_master(root, state)
        if not np.array_equal(point_file['geoids'], master.GEOID20.to_numpy()):
            raise ValueError('Coordinate ordering differs')
        origin = point_file['origin']
        moments = np.array([polygon_moments(geometry, origin) for geometry in atoms.geometry])
        area, perimeter = atoms.geometry.area.to_numpy(), atoms.geometry.length.to_numpy()
        if not np.allclose(moments[:, 0], area, rtol=1e-10, atol=1e-6):
            raise ValueError('Polygon area integration differs from geometry')
        centroids = atoms.geometry.centroid
        if not np.allclose(moments[:, 1:3] / area[:, None], np.column_stack([centroids.x, centroids.y]) - origin, rtol=1e-10, atol=1e-5):
            raise ValueError('Polygon centroid integration differs from geometry')
        phi = (atoms.population.to_numpy()[left] + atoms.population.to_numpy()[right]) / (area[left] + area[right])
        weighted_length = length * np.sqrt(phi)
        density_bounds = np.quantile(phi, np.linspace(0, 1, 6))
        density_bin = np.searchsorted(density_bounds[1:-1], phi, side='right')
        outer_formula = float(perimeter.sum() - 2 * length.sum())
        outer_direct = float(shapely.length(shapely.union_all(atoms.geometry.to_numpy())))
        if not np.isclose(outer_formula, outer_direct, rtol=1e-10, atol=1e-4):
            raise ValueError('Measurement exterior perimeter mismatch')
        grouped, county_ids, county_names, atom_index, county_index = load_county_moments(root, state, master, point_file['coordinates'], origin, atoms, records)
        grouped_arrays = [grouped[name].to_numpy() for name in ['population', 'sx', 'sy', 'q']]
        state_rows, contributions = [], []
        manifest = 'tx_shared45000_continuation_20261103/shared_070000/manifest.json' if state == 'tx' else 'nc_primary_continuation/snapshot_003/manifest.json'
        specs = json.loads((root / CAMPAIGN / manifest).read_text())['experiments']
        sampler_cuts = {}
        for group, spec in specs.items():
            tag = f"{spec['epsilon']:g}".replace('.', 'p')
            for seed in spec['seeds']:
                pattern = f"{spec['prefix']}_chain_eps{tag}_seed{seed}_steps*.csv"
                for path in (root / spec['input_dir']).glob(pattern):
                    records[str(path.relative_to(root))] = sha(path)
                    with path.open() as stream:
                        for row in csv.DictReader(stream):
                            step = int(row['step'])
                            if step >= spec['steps'] or step % 100 != 99:
                                continue
                            key = group, seed, step
                            if key in sampler_cuts:
                                raise ValueError('Overlapping sampler traces')
                            sampler_cuts[key] = int(row['cut_edges']), row['plan_hash']
        node_maps = {}
        for group, spec in specs.items():
            frame = gpd.read_file(root / spec['dataset'], layer='precincts', ignore_geometry=True)
            lookup = dict(zip(frame.UNIQUE_ID, range(len(frame))))
            node_maps[group] = np.array([lookup[unit] for unit in atoms.unit])

        def evaluate(labels, base):
            labels = np.asarray(labels, dtype=int)
            cut = labels[left] != labels[right]
            pp, district_area, district_perimeter = boundary_scores(area, perimeter, (left, right, length), labels)
            area_radius, _ = moment_radius(*moments.T, labels)
            pop_radius, _ = moment_radius(atoms.population.to_numpy(), atoms.sx.to_numpy(), atoms.sy.to_numpy(), atoms.q.to_numpy(), labels)
            if not np.isclose(pop_radius, base['normalized_rms_radius'], rtol=1e-12, atol=1e-12) or not np.isclose(pp.mean(), base['mean_polsby_popper'], rtol=1e-12, atol=1e-12):
                raise ValueError('Previous geographic score changed')
            internal = float(length[cut].sum())
            if not np.isclose(district_perimeter.sum(), outer_direct + 2 * internal, rtol=1e-10, atol=1e-4):
                raise ValueError('Internal/exterior perimeter identity failed')
            contribution = county_contributions(*grouped_arrays, county_index, atom_index, labels, atoms)
            if not np.isclose(contribution.sum(), pop_radius ** 2, rtol=1e-11, atol=1e-12):
                raise ValueError('County attribution does not recover population dispersion')
            row = {key: base[key] for key in ['state', 'group', 'seed', 'step', 'plan_hash', 'silhouette', 'normalized_rms_radius', 'mean_polsby_popper']}
            native = None if base['group'].startswith('enacted') else sampler_cuts[(base['group'], int(base['seed']), int(base['step']))][0]
            row.update({'sampler_cut_edges': native, 'internal_boundary_km': internal / 1000, 'common_cut_edges': int(cut.sum()), 'density_weighted_boundary': float(weighted_length[cut].sum()),
                'area_normalized_rms_radius': area_radius, 'area_weighted_polsby_popper': float(np.average(pp, weights=district_area)), 'median_polsby_popper': float(np.median(pp)),
                'boundary_length_weighted_density_per_km2': float(np.average(phi[cut], weights=length[cut]) * 1e6), 'exterior_share_of_total_district_perimeter': float(outer_direct / district_perimeter.sum())})
            rows.append(row)
            state_rows.append(row)
            contributions.append(contribution)
            for number in range(5):
                available = density_bin == number
                selected = cut & available
                boundaries.append({key: row[key] for key in ['state', 'group', 'seed', 'step']} | {'density_bin': number + 1, 'lower_density_per_km2': float(density_bounds[number] * 1e6), 'upper_density_per_km2': float(density_bounds[number + 1] * 1e6), 'available_edges': int(available.sum()), 'cut_edges': int(selected.sum()), 'available_boundary_km': float(length[available].sum() / 1000), 'cut_boundary_km': float(length[selected].sum() / 1000)})

        for base in prior_scores[prior_scores.state == state].to_dict('records'):
            if base['group'].startswith('enacted'):
                year = base['group'].split('_')[-1]
                labels = atoms[f'enacted_{year}'].to_numpy()
            else:
                group, spec = base['group'], specs[base['group']]
                seed, boundary = int(base['seed']), int(base['step']) + 1
                tag = f"{spec['epsilon']:g}".replace('.', 'p')
                name = f"{spec['prefix']}_checkpoint_eps{tag}_seed{seed}_next{boundary}.pkl"
                directories = [root / CAMPAIGN / group / 'checkpoints', root / 'outputs/analysis/rebuild_campaign_2026-11-02' / group / 'checkpoints']
                if group == 'tx_dispersed':
                    directories = [root / CAMPAIGN / 'texas_independent_dispersed/checkpoints']
                paths = [directory / name for directory in directories if (directory / name).is_file()]
                hashes = {sha(path) for path in paths}
                expected = {records[str(path.relative_to(root))] for path in paths if str(path.relative_to(root)) in records}
                if not paths or len(hashes) != 1 or hashes != expected:
                    raise ValueError('Missing or changed checkpoint')
                with paths[0].open('rb') as stream:
                    checkpoint = pickle.load(stream)
                if checkpoint['seed'] != seed or checkpoint['next_step'] != boundary or checkpoint['plan_hash'] != base['plan_hash']:
                    raise ValueError('Checkpoint identity differs')
                labels = np.array([checkpoint['assignment'][int(node)] for node in node_maps[group]], dtype=int)
            evaluate(labels, base)
        state_table = pd.DataFrame(state_rows)
        array = np.array(contributions)
        county_population = master.groupby(master.GEOID20.str[:5]).TOTPOP.sum()
        retained = (~state_table.group.str.startswith('enacted')) & (state_table.step >= 500)
        for cohort in ['joint', *sorted(specs)]:
            mask = retained & ((state_table.group == cohort) if cohort != 'joint' else True)
            mean = array[mask].mean(axis=0)
            for base_index in state_table.index[state_table.group.str.startswith('enacted')]:
                for county, value, enacted_value in zip(county_ids, mean, array[base_index]):
                    county_means.append({'state': state, 'cohort': cohort, 'enacted': state_table.loc[base_index, 'group'], 'county_fips': county, 'county': county_names[county], 'population': int(county_population[county]), 'ensemble_contribution': float(value), 'enacted_contribution': float(enacted_value), 'enacted_minus_ensemble': float(enacted_value - value)})
        for (cohort, seed), chain in state_table[retained].groupby(['group', 'seed']):
            ordered = chain.sort_values('step').index.to_numpy()
            split = len(ordered) // 2
            first, second = array[ordered[:split]].mean(axis=0), array[ordered[split:]].mean(axis=0)
            for county, a, b in zip(county_ids, first, second):
                county_halves.append({'state': state, 'cohort': cohort, 'seed': int(seed), 'county_fips': county, 'county': county_names[county], 'first_mean': float(a), 'second_mean': float(b), 'second_minus_first': float(b - a), 'first_half_last_step': int(chain.sort_values('step').iloc[split - 1].step), 'second_half_first_step': int(chain.sort_values('step').iloc[split].step)})
        checks.append({'state': state, 'polygon_moments_checked': len(atoms), 'exterior_perimeter_formula_m': outer_formula, 'exterior_perimeter_direct_m': outer_direct, 'zero_population_edges': int((phi == 0).sum()), 'density_quantile_bounds_per_km2': (density_bounds * 1e6).tolist(), 'all_county_identities_checked': len(state_table)})
        print(state, 'complete', len(state_table), flush=True)
    table = pd.DataFrame(rows)
    table.to_csv(output / 'scores.csv', index=False)
    pd.DataFrame(boundaries).to_csv(output / 'density_bins.csv', index=False)
    pd.DataFrame(county_means).to_csv(output / 'county_contributions.csv', index=False)
    pd.DataFrame(county_halves).to_csv(output / 'county_half_shifts.csv', index=False)
    comparisons, diagnostics, correlations, halves = [], [], [], []
    for state, subset in table.groupby('state'):
        simulated = subset[(~subset.group.str.startswith('enacted')) & (subset.step >= 500)]
        for cohort in ['joint', *sorted(simulated.group.unique())]:
            selected = simulated if cohort == 'joint' else simulated[simulated.group == cohort]
            for metric in METRICS:
                samples = np.stack([chain.sort_values('step')[metric].to_numpy() for _, chain in selected.groupby(['group', 'seed'])])
                diagnostics.append({'state': state, 'cohort': cohort, 'metric': metric, 'chains': samples.shape[0], 'checkpoints_per_chain': samples.shape[1], 'rhat': finite_call(lambda: az.rhat(samples, method='rank')), 'bulk_ess': finite_call(lambda: az.ess(samples, method='bulk')), 'tail_ess': finite_call(lambda: az.ess(samples, method='tail')), 'mcse_mean': finite_call(lambda: az.mcse(samples, method='mean'))})
                halves.append({'state': state, 'cohort': cohort, 'metric': metric, **half_comparison(samples)})
                for plan in subset[subset.group.str.startswith('enacted')].to_dict('records'):
                    x = selected[metric].to_numpy()
                    comparisons.append({'state': state, 'cohort': cohort, 'enacted': plan['group'], 'metric': metric, 'value': plan[metric], 'median': float(np.median(x)), 'q05': float(np.quantile(x, .05)), 'q95': float(np.quantile(x, .95)), 'at_or_below': int(np.sum(x <= plan[metric])), 'at_or_above': int(np.sum(x >= plan[metric])), 'checkpoints': len(x)})
            names = [*METRICS, 'sampler_cut_edges', 'silhouette', 'normalized_rms_radius', 'mean_polsby_popper']
            matrix = selected[names].corr(method='spearman')
            for i, first in enumerate(names):
                for second in names[i + 1:]:
                    correlations.append({'state': state, 'cohort': cohort, 'first': first, 'second': second, 'spearman': float(matrix.loc[first, second])})
    result = {'sources': SOURCES, 'method': 'Existing checkpoint assignments only. Boundary weights and common measurement graph are used for scoring, never for proposals or acceptance. County contributions add to squared normalized population RMS radius. Uniform-area radius integrates the full polygon interiors, including subtraction of holes.', 'research_ready': False, 'freeze_changed': False, 'comparisons': comparisons, 'diagnostics': diagnostics, 'correlations': correlations, 'halves': halves, 'validation_checks': checks, 'previous_results_sha256': sha(geographic_review / 'results.json'), 'previous_scores_sha256': sha(geographic_review / 'scores.csv'), 'code_sha256': sha(__file__), 'input_checksums': records, 'packages': {name: metadata.version(name) for name in ['numpy', 'scipy', 'arviz', 'geopandas', 'shapely']}}
    (output / 'results.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    print(output, 'complete', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--measurement-cache', type=Path, required=True)
    parser.add_argument('--geographic-review', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    run(args.source_root.resolve(), args.measurement_cache, args.geographic_review, args.output_dir)


if __name__ == '__main__':
    main()
