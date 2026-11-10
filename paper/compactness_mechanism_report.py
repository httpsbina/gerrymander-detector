"""Render the boundary-weighting and county-attribution comparisons."""

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import geopandas as gpd
import numpy as np
import pandas as pd

from paper.compactness_mechanisms import METRICS
from paper.geographic_clustering import sha

NAMES = {'internal_boundary_km': 'Internal boundary, km', 'common_cut_edges': 'Common-graph cut adjacencies',
         'density_weighted_boundary': 'Density-weighted boundary', 'area_normalized_rms_radius': 'Uniform-area radius',
         'area_weighted_polsby_popper': 'Area-weighted Polsby-Popper', 'median_polsby_popper': 'Median district Polsby-Popper'}
COLORS = {'tx_rebuild': '#d78a38', 'tx_dispersed': '#3e8cb5', 'nc_block_union_2023': '#d78a38', 'nc_block_union_2025': '#3e8cb5'}
LABELS = {'tx_rebuild': 'Baseline starts', 'tx_dispersed': 'Dispersed starts', 'nc_block_union_2023': '2023 starts', 'nc_block_union_2025': '2025 starts'}


def render(directory, text_only=False):
    target = directory / 'boundary_comparison.png'
    if target.exists() and not text_only:
        raise FileExistsError(target)
    result = json.loads((directory / 'results.json').read_text())
    partition = json.loads((directory / 'partition_sensitivity.json').read_text())
    texas_partition = next(item for item in partition['enacted_plans'] if item['state'] == 'tx')
    table = pd.read_csv(directory / 'scores.csv')
    bins = pd.read_csv(directory / 'density_bins.csv')
    simulated = table[(~table.group.str.startswith('enacted')) & (table.step >= 500)]
    enacted = table[table.group.str.startswith('enacted')]
    comparisons = pd.DataFrame(result['comparisons'])
    comparisons.to_csv(directory / 'comparisons.csv', index=False)
    if not text_only:
        fig, axes = plt.subplots(2, 3, figsize=(14, 8))
        for row, state in enumerate(('tx', 'nc')):
            values = simulated[simulated.state == state]
            plans = enacted[enacted.state == state]
            for group, part in values.groupby('group'):
                axes[row, 0].scatter(part.common_cut_edges, part.internal_boundary_km, s=5, alpha=.12, color=COLORS[group], label=LABELS[group])
                axes[row, 1].scatter(part.area_normalized_rms_radius, part.normalized_rms_radius, s=5, alpha=.12, color=COLORS[group], label=LABELS[group])
            for plan in plans.to_dict('records'):
                color = 'black' if plan['group'].endswith('2025') else '#b5253c'
                label = plan['group'].replace('_', ' ')
                axes[row, 0].scatter(plan['common_cut_edges'], plan['internal_boundary_km'], s=100, marker='*', color=color, label=label)
                axes[row, 1].scatter(plan['area_normalized_rms_radius'], plan['normalized_rms_radius'], s=100, marker='*', color=color, label=label)
            selected = bins[(bins.state == state) & (~bins.group.str.startswith('enacted')) & (bins.step >= 500)].copy()
            selected['cut_rate'] = selected.cut_edges / selected.available_edges
            by_bin = selected.groupby('density_bin').cut_rate
            median, low, high = by_bin.median(), by_bin.quantile(.05), by_bin.quantile(.95)
            axes[row, 2].plot(median.index, median, color='#3e8cb5', label='Ensemble median')
            axes[row, 2].fill_between(median.index, low, high, color='#3e8cb5', alpha=.2, label='5th to 95th percentile')
            for group, part in bins[(bins.state == state) & bins.group.str.startswith('enacted')].groupby('group'):
                part = part.sort_values('density_bin')
                axes[row, 2].plot(part.density_bin, part.cut_edges / part.available_edges, marker='o', color='black' if group.endswith('2025') else '#b5253c', label=group.replace('_', ' '))
            for col, title in enumerate(['Counting versus measuring boundaries', 'Area versus population dispersion', 'Cut rate by local population density']):
                axes[row, col].set_title(('Texas' if state == 'tx' else 'NC') + '\n' + title, fontsize=10)
                axes[row, col].legend(fontsize=6)
            if state == 'tx':
                axes[row, 0].annotate(f"{texas_partition['within_simulation_unit_cuts']} enacted cuts\ninside simulation units", xy=(texas_partition['all_cut_adjacencies'], float(plans.internal_boundary_km.iloc[0])), xytext=(-12, 30), textcoords='offset points', ha='right', fontsize=7, arrowprops={'arrowstyle': '->', 'linewidth': .6})
            axes[row, 0].set_xlabel('Cut adjacencies on common measurement graph')
            axes[row, 0].set_ylabel('Internal boundary length, km')
            axes[row, 1].set_xlabel('Normalized uniform-area RMS radius')
            axes[row, 1].set_ylabel('Normalized population RMS radius')
            axes[row, 2].set_xlabel('Fixed density bin: low to high')
            axes[row, 2].set_ylabel('Fraction of available adjacencies cut')
            axes[row, 2].set_xticks(range(1, 6))
        fig.suptitle('Geographic weighting on the same saved assignments; no votes or party labels')
        fig.tight_layout()
        fig.savefig(target, dpi=190)
        plt.close(fig)
    counties = pd.read_csv(directory / 'county_contributions.csv')
    joint = counties[counties.cohort == 'joint']
    fig, axes = plt.subplots(1, 3, figsize=(14, 5))
    top_records = []
    for ax, (state, year) in zip(axes, [('tx', 2025), ('nc', 2023), ('nc', 2025)]):
        part = joint[(joint.state == state) & (joint.enacted == f'enacted_{year}')].nlargest(6, 'enacted_minus_ensemble')
        top_records.extend(part.to_dict('records'))
        ax.barh(part.county.str.title().iloc[::-1], part.enacted_minus_ensemble.iloc[::-1], color='#3e8cb5')
        ax.set_title(('Texas' if state == 'tx' else 'NC') + f' {year}')
        ax.set_xlabel('Contribution to enacted-minus-ensemble\nsquared normalized population radius')
    fig.suptitle('Largest positive county contributions to the population-dispersion gap')
    fig.tight_layout()
    if not text_only:
        fig.savefig(directory / 'county_contributions.png', dpi=190)
    plt.close(fig)
    pd.DataFrame(top_records).to_csv(directory / 'largest_county_contributions.csv', index=False)
    halves = pd.read_csv(directory / 'county_half_shifts.csv')
    totals = halves.groupby(['state', 'cohort', 'seed'], as_index=False).second_minus_first.sum()
    totals.to_csv(directory / 'chain_half_shift_totals.csv', index=False)
    largest = totals[totals.state == 'tx'].sort_values('second_minus_first', ascending=False).iloc[0]
    leading = halves[(halves.state == 'tx') & (halves.cohort == largest.cohort) & (halves.seed == largest.seed)].nlargest(5, 'second_minus_first')
    chain = simulated[(simulated.state == 'tx') & (simulated.group == largest.cohort) & (simulated.seed == largest.seed)].sort_values('step')
    split = len(chain) // 2
    first_mean, second_mean = chain.normalized_rms_radius.iloc[:split].mean(), chain.normalized_rms_radius.iloc[split:].mean()
    lines = ['# Why the geographic measures differ', '', 'I scored the same frozen assignments with alternative boundary and area weightings, while keeping the original chains and numerical freezes unchanged. The comparison uses all retained saved checkpoints after the existing 500-state warmup.', '', '| Map | Measure | Enacted | Simulated median | Sampled values at or below enacted |', '| --- | --- | ---: | ---: | ---: |']
    for item in result['comparisons']:
        if item['cohort'] != 'joint':
            continue
        label = ('Texas' if item['state'] == 'tx' else 'NC') + ' ' + item['enacted'].split('_')[-1]
        digits = 0 if item['metric'] == 'common_cut_edges' else (1 if item['metric'] in ['internal_boundary_km', 'density_weighted_boundary'] else 4)
        lines.append(f"| {label} | {NAMES[item['metric']]} | {item['value']:,.{digits}f} | {item['median']:,.{digits}f} | {item['at_or_below']} / {item['checkpoints']} |")
    failed_rows = []
    diagnostic_rows = []
    for item in result['diagnostics']:
        threshold = max(400, 100 * item['chains'])
        passed = all(item[key]['status'] == 'finite' for key in ['rhat', 'bulk_ess', 'tail_ess', 'mcse_mean']) and item['rhat']['value'] < 1.01 and item['bulk_ess']['value'] >= threshold and item['tail_ess']['value'] >= threshold
        row = {key: item[key] for key in ['state', 'cohort', 'metric', 'chains', 'checkpoints_per_chain']}
        row.update({key: item[key]['value'] for key in ['rhat', 'bulk_ess', 'tail_ess', 'mcse_mean']})
        row.update({'reference_ess_minimum': threshold, 'passes_reference_screens': passed})
        diagnostic_rows.append(row)
        if not passed:
            failed_rows.append(row)
    pd.DataFrame(diagnostic_rows).to_csv(directory / 'diagnostics.csv', index=False)
    lines.extend(['', 'Internal boundary length is shorter for all three enacted maps than for every retained checkpoint, even though cut-adjacency counts are higher than their simulated medians. Counting crossings and measuring their physical length therefore give different assessments of the same boundaries.', '', 'Density-weighted boundary length also remains below the simulated median for every enacted map, so this weighting does not reverse the perimeter result. Texas uniform-area radius is much less unusual than its population radius. The median district Polsby-Popper score remains above every retained checkpoint for all three maps; the perimeter advantage is not confined to the arithmetic mean.', '', '## County contributions', '', 'I decomposed squared normalized population radius into additive county contributions, then compared each enacted contribution with its ensemble mean. The largest positive contributions are:'])
    for state, year in [('tx', 2025), ('nc', 2023), ('nc', 2025)]:
        part = joint[(joint.state == state) & (joint.enacted == f'enacted_{year}')].nlargest(5, 'enacted_minus_ensemble')
        entries = '; '.join(f"{row.county.title()} {row.enacted_minus_ensemble:.6f}" for row in part.itertuples())
        lines.extend(['', ('Texas' if state == 'tx' else 'NC') + f' {year}: ' + entries + '.'])
    names = ', '.join(leading.county.str.title())
    lines.extend(['', f"Texas seed {int(largest.seed)} has the largest positive half-history change in squared population radius. Its mean radius moves from {first_mean:.6f} to {second_mean:.6f}; {names} contribute the largest increases. County half-history differences add exactly to the change in mean squared radius, rather than the change in mean radius.", '', '## Methods and checks', '', 'The boundary comparison uses the common Census-block measurement graph, with physical length and adjacent-pair population density fixed across all plans. Stored sampler cut-edge counts are retained only for simulated plans; enacted comparisons use the common measurement graph because Texas assignments split simulation units. Uniform-area radius integrates the polygon interiors, preserving components and subtracting holes. County moments use every block’s 2020 Census population and centroid.', '', 'I checked polygon areas and centroids against the geometry engine, the fixed-state-boundary perimeter identity for every assignment, and the county sum identity for every assignment. results.json includes rank-normalized split R-hat, bulk and tail ESS, mean MCSE and half-history checks for every new measure and starting-map cohort. warmup_sensitivity.json retains the existing 0, 250, 500 and 1,000 warmup comparisons.', '', 'The measurement choices are described in [geographic_measures.md](../../../docs/geographic_measures.md), with the primary references [Tapp](https://arxiv.org/html/2501.02325) and [Barnes and Solomon](https://arxiv.org/html/1803.02857).', '', '## Limitations', '', 'These are descriptive comparisons within the implemented ensemble; they do not identify intent or establish legal compliance. The original geographic radius and silhouette have unresolved convergence, which also limits interpretation of their county attribution. Alternative weightings are sensitivity measurements, not new acceptance rules or changes to the sampler. Uniform-area measurements include source water areas, and population radius still represents residents by block centroids. County contributions can offset one another and are not causal effects. All ranks and counts describe the saved checkpoint series, rather than calibrated probabilities.', '', '## Reproducing', '', '```sh', 'nice -n 15 env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 MPLCONFIGDIR=.venv/matplotlib python -m paper.compactness_mechanisms --source-root SOURCE_CHECKOUT --measurement-cache MEASUREMENT_CACHE --geographic-review paper/reviews/geographic-validation-20261109/validated --output-dir NEW_REPORT_DIRECTORY', 'MPLCONFIGDIR=.venv/matplotlib python -m paper.check_compactness_mechanisms --source-root SOURCE_CHECKOUT --review-dir NEW_REPORT_DIRECTORY', 'MPLCONFIGDIR=.venv/matplotlib python -m paper.compactness_partition_check --review-dir NEW_REPORT_DIRECTORY --measurement-cache MEASUREMENT_CACHE', 'MPLCONFIGDIR=.venv/matplotlib python -m paper.compactness_mechanism_report NEW_REPORT_DIRECTORY --measurement-cache MEASUREMENT_CACHE', 'MPLCONFIGDIR=.venv/matplotlib python -m paper.check_compactness_mechanisms --source-root SOURCE_CHECKOUT --review-dir NEW_REPORT_DIRECTORY --measurement-cache MEASUREMENT_CACHE --county-distances-only', 'python -m unittest discover -s tests -v', '```', '', 'NEW_REPORT_DIRECTORY must be new. The measurement cache is produced by paper/geographic_geometry.py, and all underlying inputs are existing research files. The result records source hashes and package versions.'])
    lines.extend(['', '## Numerical reference screens', '', '| State | Cohort | Measure | R-hat | Bulk ESS | Tail ESS | Reference ESS |', '| --- | --- | --- | ---: | ---: | ---: | ---: |'])
    for row in failed_rows:
        lines.append(f"| {row['state'].upper()} | {row['cohort']} | {NAMES[row['metric']]} | {row['rhat']:.4f} | {row['bulk_ess']:.1f} | {row['tail_ess']:.1f} | {row['reference_ess_minimum']} |")
    lines.extend(['', 'The table lists every new metric and cohort combination that misses the original numerical reference screens; diagnostics.csv retains the complete set. These screens are comparisons for the new measurements, with the original freezes unchanged.'])
    numerical_start = lines.index('## Numerical reference screens') - 1
    limitation_start = lines.index('## Limitations') - 1
    lines = lines[:limitation_start] + lines[numerical_start:] + lines[limitation_start:numerical_start]
    (directory / 'README.md').write_text('\n'.join(lines) + '\n')
    notes = ['# Geographic comparison update', '', 'I compared the same saved assignments with different geographic weightings; no votes or party labels enter these calculations.', '', f"Texas has more raw cut adjacencies than every saved checkpoint, though {texas_partition['within_simulation_unit_cuts']} of those cuts lie inside simulation units where the stored maps cannot cut. Its between-unit component is {texas_partition['between_simulation_unit_cuts']:,}; {texas_partition['neutral_between_unit_at_or_above_enacted']} of {texas_partition['neutral_checkpoints']:,} checkpoints have at least that many. Its total internal boundary is shorter than every saved checkpoint. Both NC maps also have shorter boundaries than every checkpoint, with cut counts above their simulated medians. Density-weighted boundary length remains low for all three enacted maps.", '', 'Area weighting changes the dispersion assessment most in Texas: its uniform-area radius falls within the simulated distribution, while its population radius exceeds every saved checkpoint. The median district perimeter compactness remains higher than every saved checkpoint in both states, so that finding survives replacing the mean with the median.', '', 'The county table identifies where the population-distance gap occurs; county_contributions.png shows the largest positive contributions. The chain half-history table shows where the unresolved Texas dispersion drift occurs.', '', '## Limitations', '', 'These comparisons remain conditional on the ensemble, with unresolved convergence for some geographic metrics. They do not establish partisan intent or a calibrated probability of gerrymandering. The original numerical freezes remain unchanged.']
    (directory / 'meeting_notes.md').write_text('\n'.join(notes) + '\n')
    (directory / 'figure_values.json').write_text(json.dumps({'comparisons': result['comparisons'], 'largest_county_contributions': top_records, 'largest_positive_texas_half_shift': {'seed': int(largest.seed), 'first_mean_radius': float(first_mean), 'second_mean_radius': float(second_mean), 'county_contributors': leading.to_dict('records')}, 'source_results_sha256': sha(directory / 'results.json'), 'source_scores_sha256': sha(directory / 'scores.csv')}, indent=2, allow_nan=False) + '\n')



def render_county_distances(directory, cache):
    target = directory / 'county_resident_distances.png'
    if target.exists():
        raise FileExistsError(target)
    table = pd.read_csv(directory / 'county_contributions.csv')
    for state in ('tx', 'nc'):
        atoms = gpd.read_file(cache / f'{state}_atoms.gpkg', layer='atoms', ignore_geometry=True)
        total = atoms.q.sum() - (atoms.sx.sum() ** 2 + atoms.sy.sum() ** 2) / atoms.population.sum()
        mask = table.state == state
        table.loc[mask, 'enacted_rms_distance_km'] = np.sqrt(table.loc[mask, 'enacted_contribution'] * total / table.loc[mask, 'population']) / 1000
        table.loc[mask, 'pooled_ensemble_rms_distance_km'] = np.sqrt(table.loc[mask, 'ensemble_contribution'] * total / table.loc[mask, 'population']) / 1000
    table.to_csv(directory / 'county_resident_distances.csv', index=False)
    fig, axes = plt.subplots(1, 3, figsize=(14, 5))
    records = []
    for ax, (state, year) in zip(axes, [('tx', 2025), ('nc', 2023), ('nc', 2025)]):
        selected = table[(table.state == state) & (table.cohort == 'joint') & (table.enacted == f'enacted_{year}')].nlargest(5, 'enacted_minus_ensemble').iloc[::-1]
        positions = np.arange(len(selected))
        ax.barh(positions - .18, selected.enacted_rms_distance_km, .35, label='Enacted', color='#444444')
        ax.barh(positions + .18, selected.pooled_ensemble_rms_distance_km, .35, label='Ensemble, pooled RMS', color='#3e8cb5')
        ax.set_yticks(positions, selected.county.str.title())
        ax.set_title(('Texas' if state == 'tx' else 'NC') + f' {year}')
        ax.set_xlabel('RMS distance to assigned district population center, km')
        records.extend(selected.to_dict('records'))
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='lower center', ncol=2, fontsize=9, frameon=False)
    fig.suptitle('County resident-distance proxy: Census-block centroids and 2020 population\nCounties selected by largest positive contribution to the statewide dispersion gap')
    fig.tight_layout(rect=(0, .07, 1, 1))
    fig.savefig(target, dpi=190)
    plt.close(fig)
    (directory / 'county_distance_figure_values.json').write_text(json.dumps({'method': 'Ensemble RMS pools squared distances across saved states and residents before taking the square root; it is not the mean of per-map RMS values. Distances are projected Euclidean distances from block centroids, not road distances.', 'counties': records}, indent=2, allow_nan=False) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--text-only', action='store_true')
    parser.add_argument('--county-only', action='store_true')
    parser.add_argument('--measurement-cache', type=Path)
    args = parser.parse_args()
    if args.county_only:
        if args.measurement_cache is None:
            parser.error('--county-only requires --measurement-cache')
        render_county_distances(args.directory, args.measurement_cache)
    else:
        render(args.directory, args.text_only)
        if args.measurement_cache is not None and not args.text_only:
            render_county_distances(args.directory, args.measurement_cache)


if __name__ == '__main__':
    main()
