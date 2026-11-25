"""Render technical and general summaries from the matched geographic/electoral records."""

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
import numpy as np
import pandas as pd

from paper.geographic_clustering import sha
from paper.parallel_analysis import DISTANCE_METRICS

COLORS = {'tx_rebuild': '#d78a38', 'tx_dispersed': '#3e8cb5', 'nc_block_union_2023': '#d78a38', 'nc_block_union_2025': '#3e8cb5'}
LABELS = {'tx_rebuild': 'Baseline starts', 'tx_dispersed': 'Dispersed starts', 'nc_block_union_2023': '2023 starts', 'nc_block_union_2025': '2025 starts'}
NAMES = {'silhouette': 'Silhouette', 'normalized_rms_radius': 'Population radius', 'mean_polsby_popper': 'Perimeter compactness', 'mean_distance_km': 'Mean distance, km', 'sd_distance_km': 'Distance SD, km', 'distance_cv': 'Pooled radial CV', 'inverse_distance_cv': 'Inverse pooled CV', 'mean_district_cv': 'Mean district CV'}


def summaries(result, table, elections, election_data):
    retained = table[(~table.group.str.startswith('enacted')) & (table.step >= 500)]
    frozen, electoral = [], []
    for state in ('tx', 'nc'):
        histories = [item for item in result['full_frozen_histories'] if item['state'] == state]
        total = sum(item['retained_states'] for item in histories)
        seat_sum = sum(item['seat_sum'] for item in histories)
        subset = retained[retained.state == state]
        for year, enacted in result['enacted_presidential_seats'][state].items():
            tail = sum(sum(int(value) for seats, value in item['seat_counts'].items() if int(seats) <= enacted) for item in histories)
            frozen.extend([{'state': state, 'enacted_year': year, 'enacted_seats': enacted, 'scope': 'full_retained_history', 'observations': total, 'mean_democratic_seats': seat_sum / total, 'at_or_below_enacted': tail}, {'state': state, 'enacted_year': year, 'enacted_seats': enacted, 'scope': 'saved_postwarmup_checkpoints', 'observations': len(subset), 'mean_democratic_seats': float(subset.democratic_seats_2024_presidential_model.mean()), 'at_or_below_enacted': int((subset.democratic_seats_2024_presidential_model <= enacted).sum())}])
        models = election_data['results'][state]['models']
        for index, model in enumerate(models):
            office = model['office']
            for cohort in ['joint', *sorted(elections[elections.state == state].group.unique())]:
                values = elections[elections.state == state]
                if cohort != 'joint':
                    values = values[values.group == cohort]
                for year, scores in election_data['results'][state]['enacted_seats'].items():
                    enacted = scores[index]
                    electoral.append({'state': state, 'cohort': cohort, 'election': office, 'enacted_year': year, 'enacted_seats': enacted, 'checkpoints': len(values), 'mean_democratic_seats': float(values[office].mean()), 'median_democratic_seats': float(values[office].median()), 'minimum': int(values[office].min()), 'maximum': int(values[office].max()), 'at_or_below_enacted': int((values[office] <= enacted).sum())})
    return frozen, electoral


def render(directory, text_only=False):
    if (directory / 'same_map_comparison.png').exists() and not text_only:
        raise FileExistsError('Refusing existing report figures')
    result = json.loads((directory / 'results.json').read_text())
    paired_result = json.loads((directory / 'paired_election_results.json').read_text())
    projection = json.loads((directory / 'projection_sensitivity.json').read_text())
    precision = json.loads((directory / 'additional_precision.json').read_text())
    unavailable_frequency = sum(item['mcse_frequency']['status'] != 'finite' for item in precision['enacted_score_frequency'])
    full_election = json.loads((directory / 'full_elections/results.json').read_text())
    table = pd.read_csv(directory / 'paired_presidential.csv')
    retained = table[(~table.group.str.startswith('enacted')) & (table.step >= 500)]
    enacted = table[table.group.str.startswith('enacted')]
    elections = pd.read_csv(directory / 'paired_all_elections.csv')
    frozen, electoral = summaries(result, table, elections, full_election)
    pd.DataFrame(frozen).to_csv(directory / 'electoral_history_scopes.csv', index=False)
    pd.DataFrame(electoral).to_csv(directory / 'all_election_summary.csv', index=False)
    rng = np.random.default_rng(20261118)
    if not text_only:
        fig, axes = plt.subplots(2, 3, figsize=(14, 8))
        for row, state in enumerate(('tx', 'nc')):
            values = retained[retained.state == state]
            plans = enacted[enacted.state == state]
            seats = values.democratic_seats_2024_presidential_model
            bins = np.arange(int(seats.min()) - .5, int(seats.max()) + 1.5)
            for group, part in values.groupby('group'):
                color = COLORS[group]
                axes[row, 0].hist(part.democratic_seats_2024_presidential_model, bins=bins, density=True, alpha=.5, label=LABELS[group], color=color)
                jitter = rng.uniform(-.12, .12, len(part))
                axes[row, 1].scatter(part.mean_distance_km, part.democratic_seats_2024_presidential_model + jitter, s=5, alpha=.12, color=color, label=LABELS[group])
                axes[row, 2].scatter(part.mean_distance_km, part.sd_distance_km, s=5, alpha=.12, color=color, label=LABELS[group])
            x = np.array([0, max(values.mean_distance_km.max(), plans.mean_distance_km.max()) * 1.05])
            axes[row, 2].plot(x, x * values.distance_cv.median(), color='#777777', linestyle=':', label='Ensemble median CV')
            for plan in plans.to_dict('records'):
                label = plan['group'].replace('_', ' ')
                color = 'black' if plan['group'].endswith('2025') else '#b5253c'
                axes[row, 0].axvline(plan['democratic_seats_2024_presidential_model'], color=color, linestyle='--', label=label)
                axes[row, 1].scatter(plan['mean_distance_km'], plan['democratic_seats_2024_presidential_model'], s=80, marker='*', color=color, label=label)
                axes[row, 2].scatter(plan['mean_distance_km'], plan['sd_distance_km'], s=80, marker='*', color=color, label=label)
            axes[row, 0].set_xlabel('Democratic-majority districts')
            axes[row, 0].set_ylabel('Density of checkpoint scores')
            axes[row, 0].xaxis.set_major_locator(MaxNLocator(integer=True))
            axes[row, 1].set_xlabel('Population mean distance to district center, km')
            axes[row, 1].set_ylabel('Democratic-majority districts')
            axes[row, 1].yaxis.set_major_locator(MaxNLocator(integer=True))
            axes[row, 2].set_xlabel('Population mean distance, km')
            axes[row, 2].set_ylabel('Population SD of distance, km')
            for col, title in enumerate(['Electoral score: saved checkpoints', 'Geography alongside electoral score', 'Mean distance and variation']):
                axes[row, col].set_title(('Texas' if state == 'tx' else 'NC') + f' ({len(values):,} saved states)\n' + title, fontsize=10)
                axes[row, col].legend(fontsize=6)
        fig.suptitle('Same-map comparison: modeled 2024 presidential votes and 2020 Census population\nSmall seat-axis jitter is for display only; every score remains integer-valued')
        fig.tight_layout()
        fig.savefig(directory / 'same_map_comparison.png', dpi=190)
        plt.close(fig)
    correlations = pd.read_csv(directory / 'all_election_associations.csv')
    heat_metrics = ['silhouette', 'normalized_rms_radius', 'mean_polsby_popper', 'mean_distance_km', 'sd_distance_km', 'distance_cv']
    if not text_only:
        for state in ('tx', 'nc'):
            offices = [item['office'] for item in full_election['results'][state]['models']]
            values = correlations[(correlations.state == state) & (correlations.cohort == 'joint') & (correlations.scope == 'pooled')].pivot(index='metric', columns='election', values='spearman').loc[heat_metrics, offices]
            fig, ax = plt.subplots(figsize=(max(10, len(offices) * .8), 5))
            image = ax.imshow(np.ma.masked_invalid(values.to_numpy()), cmap='coolwarm', vmin=-1, vmax=1, aspect='auto')
            ax.set_xticks(range(len(offices)), offices, rotation=45, ha='right', fontsize=8)
            ax.set_yticks(range(len(heat_metrics)), [NAMES[item] for item in heat_metrics], fontsize=9)
            for i in range(len(heat_metrics)):
                for j in range(len(offices)):
                    value = values.iloc[i, j]
                    ax.text(j, i, f'{value:.2f}' if np.isfinite(value) else 'NA', ha='center', va='center', fontsize=8)
            fig.colorbar(image, ax=ax, label='Descriptive Spearman correlation')
            ax.set_title(('Texas' if state == 'tx' else 'NC') + ': geography and seat scores across existing 2024 elections\nSame frozen checkpoints; coefficients do not establish independence or causation')
            fig.tight_layout()
            fig.savefig(directory / f'{state}_election_associations.png', dpi=190)
            plt.close(fig)
    responsiveness = paired_result['responsiveness']
    if not text_only:
        fig, axes = plt.subplots(1, 2, figsize=(14, 5.5))
        for ax, state in zip(axes, ('tx', 'nc')):
            values = [item for item in responsiveness if item['state'] == state]
            x = np.array([item['statewide_democratic_two_party_share'] * 100 for item in values])
            med = np.array([item['median'] for item in values])
            low, high = np.array([item['minimum'] for item in values]), np.array([item['maximum'] for item in values])
            ax.errorbar(x, med, yerr=[med - low, high - med], fmt='o', color='#3e8cb5', capsize=3, label='Ensemble median and observed range')
            for year in values[0]['enacted']:
                actual = [item['enacted'][year] for item in values]
                ax.scatter(x, actual, marker='x' if year == '2023' else '+', s=65, color='#b5253c' if year == '2023' else 'black', label=f'Enacted {year}', zorder=4)
            for item, xx, yy in zip(values, x, med):
                if item['election'] in ['President', 'Governor', 'US Senate']:
                    ax.annotate(item['election'], (xx, yy), xytext=(5, 5), textcoords='offset points', fontsize=8)
            ax.set_title(('Texas' if state == 'tx' else 'NC') + f': {len(values)} existing elections')
            ax.set_xlabel('Statewide Democratic two-party vote share, %')
            ax.set_ylabel('Democratic-majority districts')
            ax.yaxis.set_major_locator(MaxNLocator(integer=True))
            ax.legend(fontsize=7)
        fig.suptitle('Election sensitivity on the full frozen checkpoint set\nSeparate statewide elections, not a fitted uniform-swing curve')
        fig.tight_layout()
        fig.savefig(directory / 'full_election_responsiveness.png', dpi=190)
        plt.close(fig)
    diag_rows = []
    for kind, items, election_field in [('distance', result['diagnostics'], False), ('election', paired_result['election_diagnostics'], True)]:
        for item in items:
            threshold = max(400, 100 * item['chains'])
            finite = all(item[key]['status'] == 'finite' for key in ['rhat', 'bulk_ess', 'tail_ess', 'mcse_mean'])
            passed = finite and item['rhat']['value'] < 1.01 and item['bulk_ess']['value'] >= threshold and item['tail_ess']['value'] >= threshold
            row = {'kind': kind, 'state': item['state'], 'cohort': item['cohort'], 'measure': item['election' if election_field else 'metric'], 'chains': item['chains'], 'checkpoints_per_chain': item['checkpoints_per_chain'], 'reference_ess_minimum': threshold, 'passes_reference_screens': passed}
            for key in ['rhat', 'bulk_ess', 'tail_ess', 'mcse_mean']:
                row[key], row[key + '_status'] = item[key]['value'], item[key]['status']
            diag_rows.append(row)
    pd.DataFrame(diag_rows).to_csv(directory / 'diagnostics.csv', index=False)
    comparison_rows = [item for item in result['comparisons'] if item['cohort'] == 'joint']
    pd.DataFrame(comparison_rows).to_csv(directory / 'distance_variation_summary.csv', index=False)
    primary_corr = pd.read_csv(directory / 'associations.csv')
    primary_corr = primary_corr[(primary_corr['sample'] == 'all_frozen_checkpoints') & (primary_corr.cohort == 'joint')]
    stability = []
    for state, values in primary_corr.groupby('state'):
        for metric, part in values.groupby('metric'):
            pooled = part[part.scope == 'pooled'].iloc[0]
            chains = part[part.scope != 'pooled']
            stability.append({'state': state, 'metric': metric, 'pooled_spearman': pooled.spearman, 'chain_minimum': float(chains.spearman.min()), 'chain_maximum': float(chains.spearman.max()), 'unavailable_chains': int((chains.status != 'finite').sum())})
    pd.DataFrame(stability).to_csv(directory / 'presidential_association_stability.csv', index=False)
    lines = ['# Parallel comparison for Gerber', '', 'I compared geographic structure and modeled electoral outcomes on the same saved maps. I used all available 100-state checkpoints after the existing 500-state warmup, while retaining the full chain histories as a separate electoral summary.', '', '## Full histories and saved checkpoints', '', '| State | Scope | Observations | Enacted score | Mean score | At or below enacted |', '| --- | --- | ---: | ---: | ---: | ---: |']
    for row in frozen:
        lines.append(f"| {row['state'].upper()} {row['enacted_year']} | {row['scope'].replace('_', ' ')} | {row['observations']:,} | {row['enacted_seats']} | {row['mean_democratic_seats']:.4f} | {row['at_or_below_enacted']:,} |")
    lines.extend(['', 'The counts describe states, including revisits. I report full histories and saved checkpoints separately. The same-map figures use saved checkpoints; their smaller tail counts do not replace the full-history findings.', '', '## Mean distance and variation', '', '| Map | Mean distance, km | SD, km | CV | Inverse CV |', '| --- | ---: | ---: | ---: | ---: |'])
    for row in enacted.to_dict('records'):
        lines.append(f"| {row['state'].upper()} {row['group'].split('_')[-1]} | {row['mean_distance_km']:.4f} | {row['sd_distance_km']:.4f} | {row['distance_cv']:.4f} | {row['inverse_distance_cv']:.4f} |")
    lines.extend(['', 'CV is the population-weighted SD of distance divided by its mean, and inverse CV is the reciprocal per-map score. Mean distance and SD can both increase while their ratio changes little. Low CV means more similar distances, rather than short distances; I retain the original distance scale alongside the ratios.', '', '## Parallel outcomes', '', 'The geographic metrics are calculated without votes. I then pair them with electoral scores by state, starting-map cohort, seed, step and plan hash, and report descriptive associations within each chain and cohort as well as jointly. The heatmaps use the full frozen checkpoint set for every existing election, including the additional Texas checkpoints beyond the earlier 45,000-state comparison.', '', 'full_election_responsiveness.png shows the observed range and median for each election, with both NC enacted plans marked. The points are different 2024 statewide contests, rather than a fitted swing curve. all_election_summary.csv records every enacted score, mean, median, range and count at or below the enacted score.', '', '## Diagnostics', '', 'diagnostics.csv records every distance and election screen by starting-map cohort and jointly, with the existing R-hat and ESS reference values. results.json and paired_election_results.json retain warmup and half-history sensitivity. Several new distance measures miss the reference screens, so the original electoral freezes do not certify the new geographic quantities.', '', '## Limitations', '', 'The reference ensemble retains its existing constraints and simulation units. Texas enacted lines can split units where sampled maps cannot, and the original Texas sampler geography retains its documented overlap warnings. Population distances use 2020 Census block centroids, while election scores use modeled block allocations of 2024 returns; these are not actual 2026 congressional results. Some geographic values lie outside the observed reference range, so I do not extrapolate a geography-adjusted electoral comparison. Correlations do not establish independence or causation, and serial dependence rules out treating the observations as IID for p-values. Finite MCSE values are not precision guarantees when convergence fails. Tail frequencies are descriptive; a constant event indicator has unavailable uncertainty rather than zero error, and the counts are not calibrated p-values. The original freezes remain unchanged.', '', '## Reproducing', '', 'The exact commands and checks are in execution.json and verification.json. The pinned environment is preserved. Full election assignment fingerprints are checked against the original graph, and an independent bincount tally checks every plan and election. Existing election scores are retained and compared with the expanded scoring. The read-only assignment audit is separate from replay or continuation certification.', '', 'The methods are in [parallel_comparison.md](../../../docs/parallel_comparison.md).'])
    place = lines.index('## Limitations') - 1
    additions = ['', f"The fixed-center projection check uses all block locations on {projection['assignments_checked']} preselected assignments. Switching from projected to GRS80 ellipsoidal distance changes mean distance by at most {projection['maximum_absolute_relative_changes']['mean_km'] * 100:.3f}% and CV by at most {projection['maximum_absolute_relative_changes']['cv'] * 100:.3f}% in that pilot; this does not re-optimize centers on the ellipsoid.", '', f"additional_precision.json retains MCSE for SD and the 5th and 95th percentiles, plus enacted-score indicator diagnostics. Frequency MCSE is unavailable in {unavailable_frequency} of {len(precision['enacted_score_frequency'])} series because the indicators are constant. These cases remain recorded."]
    lines = lines[:place] + additions + lines[place:]
    (directory / 'README.md').write_text('\n'.join(lines) + '\n')
    general = ['# Results for discussion', '', 'I ask two questions about the Texas and North Carolina maps: what electoral outcomes their boundaries produce when votes stay fixed, and how they group people geographically. I compare each enacted map with the same reference ensemble.', '']
    for state in ('tx', 'nc'):
        row = next(item for item in frozen if item['state'] == state and item['scope'] == 'full_retained_history')
        general.append(f"Using the modeled 2024 presidential vote, {'Texas' if state == 'tx' else 'NC'} scores {row['enacted_seats']} Democratic-majority districts under the enacted map, compared with a reference mean of {row['mean_democratic_seats']:.2f}. There are {row['at_or_below_enacted']:,} states at or below that score among {row['observations']:,} retained observations.")
    general.extend(['', '| Map | Mean distance, km | Reference median, km | CV | Reference median CV |', '| --- | ---: | ---: | ---: | ---: |'])
    for row in enacted.to_dict('records'):
        dist = next(item for item in comparison_rows if item['state'] == row['state'] and item['enacted'] == row['group'] and item['metric'] == 'mean_distance_km')
        cv = next(item for item in comparison_rows if item['state'] == row['state'] and item['enacted'] == row['group'] and item['metric'] == 'distance_cv')
        general.append(f"| {row['state'].upper()} {row['group'].split('_')[-1]} | {row['mean_distance_km']:.2f} | {dist['median']:.2f} | {row['distance_cv']:.3f} | {cv['median']:.3f} |")
    governor = next(item for item in responsiveness if item['state'] == 'nc' and item['election'] == 'Governor')
    tx_offices = [item for item in responsiveness if item['state'] == 'tx']
    tx_enacted = sorted(set(value for item in tx_offices for value in item['enacted'].values()))
    general.extend(['', f"Texas scores {tx_enacted[0]} Democratic-majority districts in all {len(tx_offices)} existing statewide contests, while their reference means range from {min(item['mean'] for item in tx_offices):.2f} to {max(item['mean'] for item in tx_offices):.2f} on the saved checkpoints.", '', f"NC's comparison changes with the election. Under the 2024 governor vote allocation, its 2023 and 2025 maps score {governor['enacted']['2023']} and {governor['enacted']['2025']} Democratic-majority districts, compared with a reference checkpoint mean of {governor['mean']:.2f}. Each comparison holds one election's vote allocation fixed."])
    general.extend(['', 'The geographic assessment depends on the property measured. Earlier calculations found shorter, more compact enacted boundaries alongside weaker population clustering. I now retain mean distance and its variation separately, since dividing SD by mean can remove a distance-scale difference.', '', 'The correlation figures show how geographic and electoral scores vary together among the saved maps, with every election retained. They do not turn the two questions into one overall verdict.', '', '## Limitations', '', 'The new geographic results remain preliminary because some convergence screens fail. The reference ensemble and modeled votes have documented constraints and input limitations. These comparisons do not establish partisan intent, legal compliance or a calibrated probability of gerrymandering.'])
    tx_plan = enacted[enacted.state == 'tx'].iloc[0]
    tx_reference = retained[retained.state == 'tx']
    general.insert(general.index('## Limitations') - 1, f"Texas's mean distance exceeds every saved checkpoint, while its CV of {tx_plan.distance_cv:.3f} falls within the reference range of {tx_reference.distance_cv.min():.3f} to {tx_reference.distance_cv.max():.3f}. The ratio describes relative variation rather than distance scale.")
    (directory / 'general_summary.md').write_text('\n'.join(general) + '\n')
    technical = ['# Technical summary', '', 'I calculate pooled population-weighted radial mean mu and population SD sigma from every Census block centroid, then retain CV = sigma / mu and inverse CV = mu / sigma. I also retain the population-weighted mean of district CVs, which differs from pooled CV. The reciprocal score does not add independent evidence.', '', 'I pair every geographic and electoral record by cohort, seed, recorded step and plan hash. The primary comparison uses every saved 100-state checkpoint after warmup 500. Full-history seat summaries use every retained CSV state and remain separately labelled. The complete election set includes all locally available statewide contests selected by the existing model.', '', 'For every new distance quantity and election seat series, I retain rank-normalized split R-hat, bulk and tail ESS, mean MCSE, half-history comparisons and warmups 0, 250, 500 and 1,000. Every unavailable diagnostic remains recorded. Associations are descriptive Spearman coefficients with per-chain and starting-map-group comparisons, without IID significance tests.', '', '## Limitations', '', 'Several distance metrics fail existing reference screens, and the input geometry and model limitations remain. The observed geometric support does not justify extrapolating a conditional electoral comparison to every enacted score. The raw and expanded election comparisons use existing data only; no chain, constraint, threshold or frozen output changes.']
    at = technical.index('## Limitations') - 1
    body = ['', '## New distance diagnostics', '', '| State | Measure | Joint R-hat | Bulk ESS | Tail ESS |', '| --- | --- | ---: | ---: | ---: |']
    for item in result['diagnostics']:
        if item['cohort'] == 'joint':
            body.append(f"| {item['state'].upper()} | {NAMES[item['metric']]} | {item['rhat']['value']:.4f} | {item['bulk_ess']['value']:.1f} | {item['tail_ess']['value']:.1f} |")
    technical = technical[:at] + body + technical[at:]
    (directory / 'STEM_summary.md').write_text('\n'.join(technical) + '\n')
    tx_mean_diag = next(item for item in result['diagnostics'] if item['state'] == 'tx' and item['cohort'] == 'joint' and item['metric'] == 'mean_distance_km')
    questions = ['# Questions for Gerber', '', f"Should geographic mixing become an additional requirement in a separate research campaign, given that Texas mean-distance R-hat is {tx_mean_diag['rhat']['value']:.4f} even though the original electoral screens passed?", '', 'How should I handle simulation-unit granularity when interpreting geographic outliers, particularly where the Texas enacted map splits units that the reference ensemble cannot split?', '', f"How should I present election-model sensitivity when NC's governor allocation gives the enacted maps {governor['enacted']['2023']} and {governor['enacted']['2025']} Democratic-majority districts against a reference mean of {governor['mean']:.2f}, while the presidential comparison points in the other direction?", '', 'Which geographic measures should be primary in a future campaign, defined before new simulations, given that CV measures relative variation rather than distance scale? I will retain all current measures and their outcomes.']
    (directory / 'questions_for_gerber.md').write_text('\n'.join(questions) + '\n')
    figure_values = {'electoral_history_scopes': frozen, 'all_election_summary': electoral, 'distance_comparisons': comparison_rows, 'presidential_association_stability': stability, 'responsiveness': responsiveness, 'projection_sensitivity': projection, 'unavailable_frequency_mcse': unavailable_frequency, 'plot_jitter_seed': 20261118, 'plot_jitter_only': True, 'source_results_sha256': sha(directory / 'results.json'), 'source_paired_election_results_sha256': sha(directory / 'paired_election_results.json'), 'source_paired_scores_sha256': sha(directory / 'paired_all_elections.csv')}
    (directory / 'figure_values.json').write_text(json.dumps(figure_values, indent=2, allow_nan=False) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--text-only', action='store_true')
    args = parser.parse_args()
    render(args.directory, args.text_only)


if __name__ == '__main__':
    main()
