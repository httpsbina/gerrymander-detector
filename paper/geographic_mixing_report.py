"""Export geographic mixing attribution from the complete saved-map records."""

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from paper.geographic_clustering import sha


def render(directory):
    if (directory / 'README.md').exists():
        raise FileExistsError(directory / 'README.md')
    result = json.loads((directory / 'results.json').read_text())
    scores = pd.read_csv(directory / 'scores.csv')
    trends = pd.read_csv(directory / 'diagnostic_trends.csv')
    windows = pd.read_csv(directory / 'chain_windows.csv')
    chains = pd.read_csv(directory / 'chain_summary.csv')
    counties = pd.read_csv(directory / 'county_windows.csv', dtype={'county_fips': str})
    omissions = pd.read_csv(directory / 'leave_one_out_attribution.csv')
    centroids = pd.read_csv(directory / 'centroid_resolution.csv')
    pd.read_csv(directory / 'graph_edge_differences.csv')
    drivers = pd.read_csv(directory / 'mean_distance_county_drivers.csv', dtype={'county_fips': str})
    unit_support = json.loads((directory / 'unit_support.json').read_text())
    half_path = Path('paper/reviews/compactness-mechanisms-20261109/county_half_shifts.csv')
    half = pd.read_csv(half_path, dtype={'county_fips': str}).rename(columns={'cohort': 'group'})
    half_records = []
    for (state, group, seed), chunk in half.groupby(['state', 'group', 'seed']):
        chain = scores[(scores.state == state) & (scores.group == group) & (scores.seed == seed)].sort_values('step')
        x = chain.normalized_rms_radius.to_numpy() ** 2
        split = len(x) // 2
        change = float(x[split:].mean() - x[:split].mean())
        if not np.isclose(chunk.second_minus_first.sum(), change, rtol=1e-9, atol=1e-12):
            raise ValueError('Previous county half attribution differs from current scores')
        absolute = float(chunk.second_minus_first.abs().sum())
        for row in chunk.to_dict('records'):
            half_records.append({**row, 'chain_squared_radius_change': change,
                                 'fraction_of_absolute_county_changes': abs(row['second_minus_first']) / absolute if absolute else None})
    half_table = pd.DataFrame(half_records)
    half_table.to_csv(directory / 'county_half_attribution.csv', index=False)
    last = trends.groupby('state').length.transform('max') == trends.length
    final = trends[last].copy()
    final['passes_reference_screens'] = (final.rhat < 1.01) & (final.bulk_ess >= final.ess_threshold) & (final.tail_ess >= final.ess_threshold)
    final.to_csv(directory / 'final_reference_screens.csv', index=False)
    changes, resolution, graph_summaries, county_shifts = [], [], [], []
    for (state, cohort, metric), series in trends.groupby(['state', 'cohort', 'metric']):
        ordered = series.sort_values('length')
        a, b = ordered.iloc[-2], ordered.iloc[-1]
        changes.append({'state': state, 'cohort': cohort, 'metric': metric, 'previous_length': int(a.length),
                        'current_length': int(b.length), 'previous_rhat': a.rhat, 'current_rhat': b.rhat,
                        'previous_bulk_ess': a.bulk_ess, 'current_bulk_ess': b.bulk_ess,
                        'previous_tail_ess': a.tail_ess, 'current_tail_ess': b.tail_ess,
                        'bulk_flat_or_decreasing': bool(b.bulk_ess <= a.bulk_ess),
                        'tail_flat_or_decreasing': bool(b.tail_ess <= a.tail_ess)})
    for (state, group, seed, county), chunk in counties.groupby(['state', 'group', 'seed', 'county_fips']):
        ordered = chunk.sort_values('window_start')
        for i in range(1, len(ordered)):
            a, b = ordered.iloc[i - 1], ordered.iloc[i]
            county_shifts.append({'state': state, 'group': group, 'seed': int(seed), 'county_fips': county, 'county': b.county,
                                  'from_window_start': int(a.window_start), 'to_window_start': int(b.window_start),
                                  'from_mean': a.mean_squared_radius_contribution, 'to_mean': b.mean_squared_radius_contribution,
                                  'shift': b.mean_squared_radius_contribution - a.mean_squared_radius_contribution})
    county_shift_table = pd.DataFrame(county_shifts)
    county_shift_table.to_csv(directory / 'county_window_changes.csv', index=False)
    pd.DataFrame(changes).to_csv(directory / 'successive_audit_changes.csv', index=False)
    for state, chunk in centroids.groupby('state'):
        selected = scores[scores.state == state]
        radius = selected.groupby(['group', 'seed']).normalized_rms_radius.mean()
        means = selected.groupby(['group', 'seed']).mean_distance_km.mean()
        resolution.append({'state': state, 'atom_mean_bias_minimum_km': float((chunk.block_mean_km - chunk.atom_mean_km).min()),
                           'atom_mean_bias_maximum_km': float((chunk.block_mean_km - chunk.atom_mean_km).max()),
                           'unit_mean_bias_minimum_km': float((chunk.block_mean_km - chunk.unit_mean_km).min()),
                           'unit_mean_bias_maximum_km': float((chunk.block_mean_km - chunk.unit_mean_km).max()),
                           'within_atom_variance_km2': float(chunk.atom_within_location_km2.mean()),
                           'within_unit_variance_km2': float(chunk.unit_within_location_km2.mean()),
                           'unit_inertia_range_km2': float(np.ptp(chunk.unit_within_location_km2)),
                           'between_chain_mean_range_km': float(np.ptp(means)),
                           'between_chain_radius_range': float(np.ptp(radius)),
                           'cohort_mean_distance_km': {key: float(value) for key, value in selected.groupby('group').mean_distance_km.mean().items()}})
        for group, subset in selected.groupby('group'):
            graph_summaries.append({'state': state, 'group': group, 'checkpoints': len(subset),
                                    **{name + '_' + stat: float(getattr(subset[name], stat)())
                                       for name in ['atomic_multiplicity_cut_excess', 'measurement_only_cuts', 'native_only_cuts']
                                       for stat in ['min', 'median', 'max']}})
    pd.DataFrame(resolution).drop(columns='cohort_mean_distance_km').to_csv(directory / 'resolution_summary.csv', index=False)
    pd.DataFrame(graph_summaries).to_csv(directory / 'graph_count_decomposition.csv', index=False)
    def number(state, cohort, metric):
        return final[(final.state == state) & (final.cohort == cohort) & (final.metric == metric)].iloc[0]
    tx = number('tx', 'joint', 'mean_distance_km')
    nc = number('nc', 'joint', 'mean_distance_km')
    baseline = number('tx', 'tx_rebuild', 'mean_distance_km')
    dispersed = number('tx', 'tx_dispersed', 'mean_distance_km')
    movement = chains[(chains.state == 'tx') & (chains.metric == 'mean_distance_km')].iloc[
        np.argmax(chains[(chains.state == 'tx') & (chains.metric == 'mean_distance_km')].half_shift.abs().to_numpy())]
    omitted = omissions[(omissions.state == 'tx') & (omissions.cohort == 'joint') & (omissions.metric == 'mean_distance_km')]
    tx_trend = trends[(trends.state == 'tx') & (trends.cohort == 'joint') & (trends.metric == 'mean_distance_km')].sort_values('length')
    before, after = tx_trend.iloc[-2], tx_trend.iloc[-1]

    colors = plt.get_cmap('tab10')
    fig, axes = plt.subplots(2, 3, figsize=(15, 8), constrained_layout=True)
    for row, state in enumerate(('tx', 'nc')):
        subset = windows[windows.state == state]
        for i, ((group, seed), chunk) in enumerate(subset.groupby(['group', 'seed'])):
            chunk = chunk.sort_values('window_start')
            x = (chunk.window_start + chunk.window_end_exclusive) / 2
            label = f'{group}: {int(seed)}'
            axes[row, 0].plot(x, chunk.mean_distance_km, marker='.', color=colors(i), label=label)
            means_squared = []
            original_chain = scores[(scores.state == state) & (scores.group == group) & (scores.seed == seed)]
            for window in chunk.itertuples():
                original_window = original_chain[(original_chain.step >= window.window_start) & (original_chain.step < window.window_end_exclusive)]
                means_squared.append(float(np.mean(original_window.normalized_rms_radius ** 2)))
            axes[row, 1].plot(x, means_squared, marker='.', color=colors(i), label=label)
        axes[row, 0].set_ylabel(state.upper() + '\nMean distance, km')
        axes[row, 1].set_ylabel('Mean squared normalized RMS radius')
        for cohort, chunk in trends[(trends.state == state) & (trends.metric == 'mean_distance_km')].groupby('cohort'):
            axes[row, 2].plot(chunk.length, chunk.rhat, marker='.', label=cohort)
        axes[row, 2].axhline(1.01, color='black', linestyle='--', label='R-hat threshold')
        axes[row, 2].set_ylabel('Mean-distance R-hat')
        axes[row, 0].legend(fontsize=6, ncol=2)
        axes[row, 2].legend(fontsize=7)
        for ax in axes[row]:
            ax.set_xlabel('Recorded states per chain')
    fig.suptitle('Geographic mixing on the existing frozen histories\nWindow means use every retained saved 100-state checkpoint; no chains omitted')
    fig.savefig(directory / 'mixing_traces.png', dpi=180)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(12, 5), constrained_layout=True)
    for ax, state in zip(axes, ('tx', 'nc')):
        chunk = scores[scores.state == state]
        for group, cohort in chunk.groupby('group'):
            ax.scatter(cohort.mean_distance_km, cohort.mean_distance_km - cohort.unit_centroid_mean_km, s=5, alpha=.25, label=group)
        ax.set(title=state.upper(), xlabel='Block-level population mean distance, km', ylabel='Underestimate from unit-centroid collapse, km')
        ax.legend(fontsize=8)
    fig.suptitle('Location aggregation changes the measurement, not the saved plan')
    fig.savefig(directory / 'unit_resolution.png', dpi=180)
    plt.close(fig)

    def table(headers, rows):
        return '\n'.join(['| ' + ' | '.join(headers) + ' |', '| ' + ' | '.join(['---'] * len(headers)) + ' |',
                          *['| ' + ' | '.join(map(str, row)) + ' |' for row in rows]])
    text = ['# Geographic mixing and simulation units',
            'I checked the geographic scores on all retained saved assignments, while keeping the original sampler, thresholds and freezes unchanged. I separated chain drift from location aggregation and graph-count differences, rather than treating every difference as a mixing problem.',
            '## Geographic convergence',
            f'Texas mean-distance R-hat is {tx.rhat:.4f} jointly, {baseline.rhat:.4f} within baseline starts and {dispersed.rhat:.4f} within dispersed starts. The failure occurs within both starting cohorts, rather than only when the cohorts are pooled. Joint split R-hat is {tx.split_rhat:.4f}, compared with folded R-hat {tx.folded_rhat:.4f}, which points mainly to location disagreement in the distributions. Mean-distance R-hat falls from {before.rhat:.4f} at {int(before.length):,} states to {after.rhat:.4f} at {int(after.length):,}, while bulk ESS increases from {before.bulk_ess:.1f} to {after.bulk_ess:.1f}; the complete trend includes reversals, so I do not extrapolate a passing chain length from it.',
            f'NC joint mean-distance R-hat is {nc.rhat:.4f}, but bulk ESS is {nc.bulk_ess:.1f} against {int(nc.ess_threshold)}. The 2023 and 2025 initialization groups still have their own failed screens in the table. The earlier electoral freeze does not certify these additional geographic measurements.',
            table(['State', 'Cohort', 'Measurement', 'R-hat', 'Bulk ESS', 'Tail ESS', 'ESS minimum'],
                  [[r.state.upper(), r.cohort, r.metric, f'{r.rhat:.4f}', f'{r.bulk_ess:.1f}', f'{r.tail_ess:.1f}', r.ess_threshold]
                   for r in final[final.metric.isin(['mean_distance_km', 'normalized_rms_radius', 'unit_centroid_mean_km'])].itertuples()]),
            'I use the full cohorts for these screens. The leave-one-out table identifies chains that contribute to disagreement, but those exploratory subsets do not replace any result or threshold. The diagnostic trends retain every 5,000-state prefix and NC’s final 23,000-state prefix; they do not create new frozen audits.',
            'The following cases have flat or decreasing bulk or tail ESS in the final two prefixes; successive_audit_changes.csv retains every case, including increases. Reciprocal CV and centroid approximations repeat related information rather than independent evidence.',
            table(['State', 'Cohort', 'Measure', 'Previous bulk ESS', 'Current bulk ESS', 'Previous tail ESS', 'Current tail ESS'],
                  [[r['state'].upper(), r['cohort'], r['metric'], f"{r['previous_bulk_ess']:.1f}", f"{r['current_bulk_ess']:.1f}",
                    f"{r['previous_tail_ess']:.1f}", f"{r['current_tail_ess']:.1f}"] for r in changes if r['bulk_flat_or_decreasing'] or r['tail_flat_or_decreasing']]),
            '## Chain movement',
            f'Texas seed {int(movement.seed)} has the largest absolute mean-distance half shift, {movement.half_shift:+.3f} km. Omitting any one Texas chain leaves joint mean-distance R-hat at or above {omitted.rhat.min():.4f}; no single omission resolves the disagreement, and every chain remains in the reported ensemble.',
            table(['State', 'Cohort', 'Seed', 'Full mean, km', 'First-half mean, km', 'Second-half mean, km', 'Shift, km', 'Lag-1 checkpoint correlation'],
                  [[r.state.upper(), r.group, int(r.seed), f'{r.mean:.3f}', f'{r.first_half_mean:.3f}', f'{r.second_half_mean:.3f}', f'{r.half_shift:+.3f}', f'{r.acf_lag_1_checkpoints:.3f}']
                   for r in chains[chains.metric == 'mean_distance_km'].itertuples()]),
            'The county records add to mean squared normalized RMS radius, not to mean distance or to the square of mean radius. Each county-window change therefore identifies where squared dispersion changes geographically, without attributing a cause to an individual boundary move.',
            table(['State', 'Cohort', 'Seed', 'Squared-radius half shift', 'Five largest absolute county changes'],
                  [[state.upper(), group, int(seed), f'{chunk.chain_squared_radius_change.iloc[0]:+.6f}',
                    '; '.join(f'{r.county} {r.second_minus_first:+.6f}' for r in chunk.loc[chunk.second_minus_first.abs().nlargest(5).index].itertuples())]
                   for (state, group, seed), chunk in half_table.groupby(['state', 'group', 'seed'])]),
            'I separately recomputed block-level mean distance in each chain’s largest adjacent-window shift and decomposed that change by county. These contributions sum to the actual change in statewide mean distance, in kilometres; the selected windows are exploratory cases from every chain, rather than a subset used for convergence. NC’s final window is shorter, with its endpoints and counts recorded.',
            table(['State', 'Seed', 'From window', 'To window', 'Mean shift, km', 'Three largest absolute county contributions, km'],
                  [[state.upper(), int(seed), f'{int(chunk.from_start.iloc[0]):,}–{int(chunk.from_end_exclusive.iloc[0]):,}',
                    f'{int(chunk.to_start.iloc[0]):,}–{int(chunk.to_end_exclusive.iloc[0]):,}', f'{chunk.global_shift_km.iloc[0]:+.3f}',
                    '; '.join(f'{r.county} {r.statewide_mean_shift_contribution_km:+.3f}' for r in chunk.loc[chunk.statewide_mean_shift_contribution_km.abs().nlargest(3).index].itertuples())]
                   for (state, group, seed), chunk in drivers.groupby(['state', 'group', 'seed'])]),
            '## Simulation units and measurement',
            'The distinct measured unit-pair graph matches the native sampler graph exactly for each state and starting cohort. Texas has additional atomic edges because the same unit pair can share more than one atom-to-atom boundary; NC has no such multiplicity. There are no unmatched unit pairs to repair in this comparison.',
            table(['State', 'Cohort', 'Native edges', 'Distinct measurement unit pairs', 'Measurement-only pairs', 'Native-only pairs', 'Extra atomic edges between units'],
                  [[r['state'].upper(), r['group'], r['native_edges'], r['measurement_unit_edges'], r['measurement_only_edges'], r['native_only_edges'], r['extra_between_unit_atomic_edges']] for r in result['graphs']]),
            'For every sampled map, I checked: atomic cut count = native cut count + atomic multiplicity excess + measurement-only cuts - native-only cuts. Counting each measured unit pair once removes atomic multiplicity from the comparison, while physical boundary length remains a separate quantity. The edge-difference table retains both endpoints and shared lengths; it does not alter adjacency.',
            table(['State', 'Maximum unit-centroid mean underestimate, km', 'Within-unit variance, km²', 'Across-chain mean range, km'],
                  [[r['state'].upper(), f"{r['unit_mean_bias_maximum_km']:.4f}", f"{r['within_unit_variance_km2']:.4f}", f"{r['between_chain_mean_range_km']:.4f}"] for r in resolution]),
            'I also checked block RMS² = unit-centroid RMS² + within-unit variance on every saved map. The within-unit term is fixed across sampled whole-unit plans, so subtracting it cannot explain chain disagreement in squared RMS. Mean distance has a different, nonlinear aggregation error, which I measure separately. The block-level scores remain the primary values.',
            table(['Map', 'Split simulation units', 'Population in split units', 'Block mean distance, km', 'Atomic-centroid mean distance, km'],
                  [[r['state'].upper() + ' ' + r['group'], r['split_simulation_units'], f"{r['population_in_split_units']:,}", f"{r['block_mean_km']:.4f}", f"{r['atom_centroid_mean_km']:.4f}"] for r in result['enacted_resolution']]),
            'I retain Texas’s enacted block assignments wherever they split simulation units. I do not assign a split unit to its majority district or present that altered map as PLANC2333.',
            table(['Map', 'Minimum population relabeling for whole units', 'Within-unit boundary, km', 'Distinct unit pairs with any cut', 'Pairs with cut and uncut contacts'],
                  [[r['state'].upper() + ' ' + r['enacted'], f"{r['minimum_population_relabeling_for_whole_units']:,}",
                    f"{r['within_unit_boundary_km']:.3f}", r['distinct_between_unit_pairs_with_any_cut'],
                    r['between_unit_pairs_with_both_cut_and_uncut_contacts']] for r in unit_support['plans']]),
            'Minimum relabeling is only a combinatorial lower bound on the population whose district would need to change if each unit had one label; it does not construct a balanced or contiguous map. A split unit can have both cut and uncut contacts with its neighbor, so even an any-cut unit-pair count does not turn Texas’s enacted assignment into a native sampler plan.',
            table(['Map', 'Any-cut unit pairs', 'Reference median', 'Reference states at or above enacted', 'Reference checkpoints'],
                  [[r['state'].upper() + ' ' + r['enacted'], r['distinct_between_unit_pairs_with_any_cut'],
                    f"{r['reference_native_cut_median']:.1f}", r['reference_distinct_pair_count_at_or_above_any_cut_statistic'],
                    r['reference_checkpoints']] for r in unit_support['plans']]),
            '## Changes that preserve the experiment',
            'I now report native graph cuts, distinct measured unit-pair cuts, atomic multiplicity and physical boundary length separately, while retaining block-level population distances. These are reporting and measurement distinctions; the saved plans and original cut-edge scores stay intact.',
            'Additional mixing would require a separately recorded continuation with the same kernel and constraints, retaining every original chain and starting-map cohort. More independent chains can improve exploration, but they do not guarantee that the existing slow chains have mixed. I have not started new simulations or altered the frozen results.',
            '## Limitations',
            'The geographic screens still have failures, so the reference ranks remain preliminary. Only saved 100-state assignments are available for these geographic calculations; checkpoint autocorrelation lags are not single ReCom steps. County contributions locate changes in mean distance and squared dispersion, without identifying a causal boundary move. Simulation units restrict which plans can be represented, while the Texas enacted map splits some of them; measurement changes cannot remove that support mismatch. The original Texas graph retains its overlap warnings, and changing that graph would change the experiment. Counts and ranks are descriptive rather than calibrated probabilities or evidence of intent.',
            '## Records',
            'results.json records input checksums and exact decomposition counts; diagnostic_trends.csv, chain_windows.csv and county_window_changes.csv retain every comparison. All chains and saved observations remain included. The verification record includes the executed commands, test results and unchanged sampler/checkpoint hashes.']
    (directory / 'README.md').write_text('\n\n'.join(text) + '\n')
    payload = {'source_results_sha256': sha(directory / 'results.json'), 'resolution': resolution,
               'graph_decomposition': graph_summaries, 'final_diagnostics': final.replace({np.nan: None}).to_dict('records'),
               'mean_distance_chains': chains[chains.metric == 'mean_distance_km'].replace({np.nan: None}).to_dict('records'),
               'county_half_source_sha256': sha(half_path), 'county_half_attribution': half_records,
               'mean_distance_county_drivers_sha256': sha(directory / 'mean_distance_county_drivers.csv'),
               'unit_support_sha256': sha(directory / 'unit_support.json'),
               'report_code_sha256': sha(__file__), 'research_ready': False}
    (directory / 'figure_values.json').write_text(json.dumps(payload, indent=2, allow_nan=False) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    render(parser.parse_args().directory)
