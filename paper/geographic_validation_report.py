"""Prepare meeting figures and tables from the completed geographic measurements."""

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import geopandas as gpd
import shapely
import numpy as np
import pandas as pd

from paper.geographic_clustering import sha

NAMES = {'silhouette': 'Silhouette', 'normalized_rms_radius': 'Normalized population RMS radius', 'mean_polsby_popper': 'Mean Polsby-Popper compactness'}
COHORTS = {'tx_rebuild': 'Baseline starts', 'tx_dispersed': 'Dispersed starts', 'nc_block_union_2023': '2023 starts', 'nc_block_union_2025': '2025 starts'}


def render(directory, measurement_cache=None, text_only=False):
    target = directory / 'geographic_comparison.png'
    if target.exists() and not text_only:
        raise FileExistsError(target)
    result = json.loads((directory / 'results.json').read_text())
    table = pd.read_csv(directory / 'scores.csv')
    simulated = table[(~table.group.str.startswith('enacted')) & (table.step >= 500)]
    enacted = table[table.group.str.startswith('enacted')]
    tx_count = int((simulated.state == 'tx').sum())
    nc_count = int((simulated.state == 'nc').sum())
    records = []
    correlations = []
    for state, subset in simulated.groupby('state'):
        matrix = subset[list(NAMES)].corr(method='spearman')
        for i, first in enumerate(NAMES):
            for second in list(NAMES)[i + 1:]:
                correlations.append({'state': state, 'first': first, 'second': second, 'spearman': float(matrix.loc[first, second])})
    pd.DataFrame(correlations).to_csv(directory / 'metric_correlations.csv', index=False)
    for plan in enacted.to_dict('records'):
        values = simulated[simulated.state == plan['state']]
        for metric, name in NAMES.items():
            x = values[metric].to_numpy()
            records.append({'state': plan['state'], 'enacted': plan['group'], 'metric': metric, 'value': plan[metric], 'simulated_median': float(np.median(x)), 'simulated_q05': float(np.quantile(x, .05)), 'simulated_q95': float(np.quantile(x, .95)), 'at_or_below': int(np.sum(x <= plan[metric])), 'at_or_above': int(np.sum(x >= plan[metric])), 'retained_checkpoints': len(x), 'direction': 'greater_or_equal' if metric == 'normalized_rms_radius' else 'less_or_equal'})
    pd.DataFrame(records).to_csv(directory / 'meeting_table.csv', index=False)
    if not text_only:
        fig, axes = plt.subplots(2, 3, figsize=(13, 7.5))
        for row, state in enumerate(('tx', 'nc')):
            for col, (metric, name) in enumerate(NAMES.items()):
                ax = axes[row, col]
                values = simulated[simulated.state == state]
                bins = np.histogram_bin_edges(values[metric], bins=25)
                for group, cohort in values.groupby('group'):
                    ax.hist(cohort[metric], bins=bins, density=True, alpha=.5, label=COHORTS[group])
                for plan in enacted[enacted.state == state].to_dict('records'):
                    year = plan['group'].split('_')[-1]
                    ax.axvline(plan[metric], color='black' if year == '2025' else '#b52b3a', linestyle='--', linewidth=1.6, label=f'Enacted {year}')
                ax.set_title(('Texas' if state == 'tx' else 'North Carolina') + '\n' + name, fontsize=10)
                ax.set_xlabel('Higher = more dispersed' if metric == 'normalized_rms_radius' else 'Higher = more compact or separated', fontsize=9)
                ax.set_ylabel('Density of saved checkpoint scores')
                ax.legend(fontsize=7)
        fig.suptitle('Geographic comparison without votes or party labels\nAll retained saved checkpoints; silhouette uses 2,048 population-sampled block locations', fontsize=12)
        fig.tight_layout()
        fig.savefig(target, dpi=200)
        plt.close(fig)
    reps = pd.read_csv(directory / 'silhouette_replications.csv')
    rep_records = []
    for (state, sample_seed, n, distance), subset in reps.groupby(['state', 'sample_seed', 'sample_size', 'distance']):
        simulated_rep = subset[~subset.group.str.startswith('enacted')]
        for plan in subset[subset.group.str.startswith('enacted')].to_dict('records'):
            for group in ['joint', *sorted(simulated_rep.group.unique())]:
                values = simulated_rep if group == 'joint' else simulated_rep[simulated_rep.group == group]
                x = values.silhouette.to_numpy()
                rep_records.append({'state': state, 'enacted': plan['group'], 'sample_seed': int(sample_seed), 'sample_size': int(n), 'distance': distance, 'cohort': group, 'value': plan['silhouette'], 'simulated_median': float(np.median(x)), 'simulated_minimum': float(x.min()), 'simulated_maximum': float(x.max()), 'at_or_below': int(np.sum(x <= plan['silhouette'])), 'checkpoints': len(x)})
    pd.DataFrame(rep_records).to_csv(directory / 'sample_sensitivity.csv', index=False)
    diag_rows = []
    for item in result['diagnostics']:
        row = {k: item[k] for k in ['state', 'group', 'metric', 'chains', 'checkpoints_per_chain', 'mean']}
        for key in ['rhat', 'bulk_ess', 'tail_ess', 'mcse_mean']:
            row[key] = item[key]['value']
            row[key + '_status'] = item[key]['status']
        diag_rows.append(row)
    pd.DataFrame(diag_rows).to_csv(directory / 'diagnostics.csv', index=False)
    lines = ['# Geographic comparison for discussion', '', f'I measured the enacted maps and every available frozen 100-state checkpoint without using votes or party labels. I retained the existing 500-state warmup, leaving {tx_count:,} Texas and {nc_count:,} NC checkpoint observations. These are saved states from correlated chains, rather than a count of independent maps.', '', '| Map | Measure | Enacted | Simulated median | Simulated 5th to 95th percentile | Sampled scores at or below enacted |', '| --- | --- | ---: | ---: | ---: | ---: |']
    for row in records:
        label = ('Texas' if row['state'] == 'tx' else 'NC') + ' ' + row['enacted'].split('_')[-1]
        lines.append(f"| {label} | {NAMES[row['metric']]} | {row['value']:.4f} | {row['simulated_median']:.4f} | {row['simulated_q05']:.4f} to {row['simulated_q95']:.4f} | {row['at_or_below']} / {row['retained_checkpoints']} |")
    lines.extend(['', 'Texas and both NC maps have higher mean perimeter compactness than every retained checkpoint, while their silhouette scores are low and their population radii are high. These measurements describe different geographic properties, so I retain the contrast rather than combining them into one score.', '', '## New-metric diagnostics', '', '| State | Measure | Joint R-hat | Bulk ESS | Tail ESS |', '| --- | --- | ---: | ---: | ---: |'])
    screen_rows = []
    for item in result['diagnostics']:
        threshold = max(400, 100 * item['chains'])
        finite = all(item[key]['status'] == 'finite' for key in ['rhat', 'bulk_ess', 'tail_ess', 'mcse_mean'])
        passed = finite and item['rhat']['value'] < 1.01 and item['bulk_ess']['value'] >= threshold and item['tail_ess']['value'] >= threshold
        screen_rows.append({'state': item['state'], 'cohort': item['group'], 'metric': item['metric'], 'reference_ess_minimum': threshold, 'reference_rhat_maximum_exclusive': 1.01, 'passes_reference_screens': passed})
        if item['group'] == 'joint':
            lines.append(f"| {item['state'].upper()} | {NAMES[item['metric']]} | {item['rhat']['value']:.4f} | {item['bulk_ess']['value']:.1f} | {item['tail_ess']['value']:.1f} |")
    pd.DataFrame(screen_rows).to_csv(directory / 'reference_screens.csv', index=False)
    lines.extend(['', 'Mean Polsby-Popper passes the original numerical reference screens within both starting-map cohorts and jointly in each state. Silhouette and radius fail one or more cohort or joint screens in both states, so the original electoral-metric freezes do not resolve geographic convergence. I have not extended or changed the frozen chains.'])
    lines.extend(['', '## What I measured', '', 'Silhouette compares average distance within a district with average distance to the nearest other district. Population RMS radius measures dispersion around each district’s population-weighted center, normalized by statewide population dispersion; I calculate it using every block’s population and centroid. Mean Polsby-Popper measures district area relative to squared perimeter, averaging the district scores. Higher silhouette and Polsby-Popper mean more separated or compact districts; higher radius means more dispersion.', '', 'I retain these three measures because they address separation, population dispersion and boundary shape. Radial CV remains in the earlier pilot, where its Texas rank changed with sample size and its interpretation was ambiguous.', '', '## Checks', '', f"The common measurement partition contains {result['measurement_inventory']['states']['tx']['measurement_atoms']:,} Texas pieces and {result['measurement_inventory']['states']['nc']['measurement_atoms']:,} NC pieces, built from all {sum(item['blocks'] for item in result['measurement_inventory']['states'].values()):,} Census blocks, including zero-population blocks. It has no positive-area overlaps, and it preserves Texas enacted splits without changing any simulation unit or graph. I checked the perimeter arithmetic against direct polygon unions for each enacted map and every terminal chain assignment.", '', 'I repeated the silhouette pilot across four independent population-sample seeds, two sample sizes and projected versus ellipsoidal distances; sample_sensitivity.csv retains every comparison. diagnostics.csv reports R-hat, bulk and tail ESS and mean Monte Carlo error for every metric, separately by starting-map cohort and jointly. results.json also retains warmup and half-history comparisons.', '', '## Limitations', '', 'The geographic results are conditional on the existing sampler, population tolerances and boundary constraints, so they describe this ensemble rather than a uniform distribution of possible maps. The original freeze does not certify convergence of these new measures; I report their diagnostics separately. Silhouette still approximates the statewide population using sampled block centroids, while the radius is population-exact only for the block-centroid representation. Repeated samples and geodesic distances assess parts of that approximation. Compactness uses a common Census-block boundary resolution, which may differ from official district polygon detail. Statewide averages can conceal individual districts, whose enacted and pilot scores are retained in district_scores.csv. An empirical zero count does not establish zero probability, and geometric unusualness does not establish partisan intent or legal noncompliance.', '', '## Reproducing', '', '```sh', 'nice -n 15 env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 python -m paper.geographic_geometry --source-root SOURCE_CHECKOUT --output-dir NEW_MEASUREMENT_CACHE', 'nice -n 15 env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 python -m paper.geographic_refinement --source-root SOURCE_CHECKOUT --measurement-cache NEW_MEASUREMENT_CACHE --output-dir NEW_REPORT_DIRECTORY', 'MPLCONFIGDIR=.venv/matplotlib python -m paper.geographic_validation_report NEW_REPORT_DIRECTORY --measurement-cache NEW_MEASUREMENT_CACHE', 'python -m unittest discover -s tests -v', '```', '', 'Both output directories must be new. results.json records source and code hashes, package versions and every diagnostic; the cache inventory records all derived-file checksums.'])
    (directory / 'README.md').write_text('\n'.join(lines) + '\n')
    if measurement_cache is not None and not text_only:
        district_table = pd.read_csv(directory / 'district_scores.csv')
        fig, axes = plt.subplots(1, 3, figsize=(14, 5))
        for ax, (state, year) in zip(axes, [('tx', 2025), ('nc', 2023), ('nc', 2025)]):
            atoms = gpd.read_file(measurement_cache / f'{state}_atoms.gpkg', layer='atoms')
            labels = atoms[f'enacted_{year}'].to_numpy(dtype=int)
            numbers = sorted(set(labels))
            geometry = [shapely.union_all(atoms.geometry.to_numpy()[labels == number]) for number in numbers]
            values = district_table[(district_table.state == state) & (district_table.group == f'enacted_{year}')].set_index('district')
            frame = gpd.GeoDataFrame({'district': numbers, 'compactness': [values.loc[number, 'polsby_popper'] for number in numbers]}, geometry=geometry, crs=5070)
            frame.plot(column='compactness', ax=ax, cmap='viridis', vmin=0, vmax=1, linewidth=.4, edgecolor='white')
            for record in frame.itertuples():
                point = record.geometry.representative_point()
                ax.text(point.x, point.y, str(record.district), fontsize=5, color='black', ha='center', bbox={'facecolor': 'white', 'alpha': .7, 'edgecolor': 'none', 'pad': .2})
            ax.set_title(('Texas' if state == 'tx' else 'NC') + f' {year}')
            ax.set_axis_off()
        colorbar = fig.colorbar(plt.cm.ScalarMappable(norm=plt.Normalize(0, 1), cmap='viridis'), ax=list(axes), shrink=.65, pad=.02)
        colorbar.set_label('District Polsby-Popper compactness')
        fig.suptitle('Enacted districts on the common Census-block measurement geography')
        fig.savefig(directory / 'enacted_geography.png', dpi=200, bbox_inches='tight')
        plt.close(fig)
    findings = {(item['state'], item['enacted'], item['metric']): item for item in records}
    nc23_silhouette = findings[('nc', 'enacted_2023', 'silhouette')]['at_or_below']
    nc25_silhouette = findings[('nc', 'enacted_2025', 'silhouette')]['at_or_below']
    nc23_radius = findings[('nc', 'enacted_2023', 'normalized_rms_radius')]['at_or_above']
    nc25_radius = findings[('nc', 'enacted_2025', 'normalized_rms_radius')]['at_or_above']
    notes = ['# Geographic results', '', f'I compared the enacted maps with all retained saved checkpoints, using no vote or party fields: {tx_count:,} Texas states and {nc_count:,} NC states. Each checkpoint is 100 chain states apart.', '', '| Map | Silhouette, enacted / median | Population radius, enacted / median | Perimeter compactness, enacted / median |', '| --- | ---: | ---: | ---: |']
    for state, year in [('tx', 2025), ('nc', 2023), ('nc', 2025)]:
        found = {item['metric']: item for item in records if item['state'] == state and item['enacted'] == f'enacted_{year}'}
        cells = [f"{found[metric]['value']:.4f} / {found[metric]['simulated_median']:.4f}" for metric in NAMES]
        notes.append('| ' + ('Texas' if state == 'tx' else 'NC') + f" {year} | " + ' | '.join(cells) + ' |')
    notes.extend(['', 'Higher silhouette means better geographic separation; higher radius means more population dispersion; higher perimeter compactness means a shorter boundary relative to area.', '', f'Texas has lower silhouette and higher radius than every retained checkpoint. For NC, {nc23_silhouette} checkpoints fall at or below the 2023 silhouette and {nc25_silhouette} at or below the 2025 silhouette; {nc23_radius} checkpoints are at least as dispersed as the 2023 map, and {nc25_radius} at least as dispersed as the 2025 map. All three enacted maps have higher mean perimeter compactness than every retained checkpoint, though.', '', 'The low silhouette ordering holds in the ten-checkpoint-per-chain pilot across four population-sample seeds, both sample sizes and projected versus geodesic distances. Radius uses every Census block’s population and centroid, and perimeter uses the same block-derived measurement geography for enacted and simulated maps.', '', '## Limitations', '', f"The new geographic metrics do not all meet the original numerical reference screens. Texas joint radius R-hat is {next(item for item in result['diagnostics'] if item['state'] == 'tx' and item['group'] == 'joint' and item['metric'] == 'normalized_rms_radius')['rhat']['value']:.4f}, with bulk ESS {next(item for item in result['diagnostics'] if item['state'] == 'tx' and item['group'] == 'joint' and item['metric'] == 'normalized_rms_radius')['bulk_ess']['value']:.1f}; the NC joint radius bulk ESS is {next(item for item in result['diagnostics'] if item['state'] == 'nc' and item['group'] == 'joint' and item['metric'] == 'normalized_rms_radius')['bulk_ess']['value']:.1f} against a 600 reference. Mean perimeter compactness passes every cohort and joint reference screen, while silhouette or radius fails one or more screens in each state. These are preliminary geographic comparisons within the constrained ensemble, rather than a probability of gerrymandering. I have kept the original freezes unchanged.", '', '## Records', '', 'The figures are geographic_comparison.png, enacted_geography.png and geographic_traces.png; chain_means.csv records each chain’s mean and half-history shift. meeting_table.csv contains the enacted values, simulated quantiles and both directional counts; diagnostics.csv and reference_screens.csv contain every cohort and joint screen. results.json, sample_sensitivity.csv and verification.json retain the calculations and checks.'])
    (directory / 'meeting_notes.md').write_text('\n'.join(notes) + '\n')
    summary = {'meeting_values': records, 'silhouette_sensitivity': rep_records, 'metric_correlations': correlations, 'source_results_sha256': sha(directory / 'results.json'), 'source_scores_sha256': sha(directory / 'scores.csv')}
    (directory / 'meeting_results.json').write_text(json.dumps(summary, indent=2, allow_nan=False) + '\n')



def render_traces(directory):
    target = directory / 'geographic_traces.png'
    if target.exists():
        raise FileExistsError(target)
    table = pd.read_csv(directory / 'scores.csv')
    table = table[(~table.group.str.startswith('enacted')) & (table.step >= 500)]
    means = []
    fig, axes = plt.subplots(2, 3, figsize=(14, 8))
    for row, state in enumerate(('tx', 'nc')):
        for col, (metric, name) in enumerate(NAMES.items()):
            ax = axes[row, col]
            for color, ((cohort, seed), chain) in enumerate(table[table.state == state].groupby(['group', 'seed'])):
                chain = chain.sort_values('step')
                x = chain[metric].to_numpy()
                split = len(x) // 2
                means.append({'state': state, 'cohort': cohort, 'seed': int(seed), 'metric': metric, 'checkpoints': len(x), 'mean': float(x.mean()), 'first_half_mean': float(x[:split].mean()), 'second_half_mean': float(x[split:].mean()), 'second_minus_first': float(x[split:].mean() - x[:split].mean())})
                binned = chain.groupby((chain.step // 1000).astype(int)).agg(step=('step', 'mean'), value=(metric, 'mean'))
                ax.plot(binned.step, binned.value, color=f'C{color}', linewidth=.9, label=str(int(seed)))
            ax.set_title(('Texas' if state == 'tx' else 'NC') + '\n' + name, fontsize=10)
            ax.set_xlabel('Recorded chain step')
            ax.set_ylabel('Mean within 1,000-state bin')
            ax.legend(ncol=4, fontsize=6)
    fig.suptitle('Geographic traces by chain: binned saved-checkpoint values, with 500-state warmup')
    fig.tight_layout()
    fig.savefig(target, dpi=180)
    plt.close(fig)
    pd.DataFrame(means).to_csv(directory / 'chain_means.csv', index=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--measurement-cache', type=Path)
    parser.add_argument('--text-only', action='store_true')
    parser.add_argument('--trace-only', action='store_true')
    args = parser.parse_args()
    if args.trace_only:
        render_traces(args.directory)
    else:
        render(args.directory, args.measurement_cache, args.text_only)
        if not args.text_only:
            render_traces(args.directory)


if __name__ == '__main__':
    main()
