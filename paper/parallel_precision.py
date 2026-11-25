"""Retain precision diagnostics for reported quantiles and enacted-score frequencies."""

import argparse
import json
from pathlib import Path

import arviz as az
import numpy as np
import pandas as pd

from paper.parallel_analysis import DISTANCE_METRICS
from paper.review_precision import finite_call, tail_diagnostics


def run(directory):
    target = directory / 'additional_precision.json'
    if target.exists():
        raise FileExistsError(target)
    distances = pd.read_csv(directory / 'paired_presidential.csv')
    distances = distances[(~distances.group.str.startswith('enacted')) & (distances.step >= 500)]
    elections = pd.read_csv(directory / 'paired_all_elections.csv')
    source = json.loads((directory / 'full_elections/results.json').read_text())
    precision, tails = [], []
    for kind, table in [('distance', distances), ('election', elections)]:
        for state, values in table.groupby('state'):
            measures = DISTANCE_METRICS if kind == 'distance' else [model['office'] for model in source['results'][state]['models']]
            for cohort in ['joint', *sorted(values.group.unique())]:
                selected = values if cohort == 'joint' else values[values.group == cohort]
                for measure in measures:
                    groups = list(selected.groupby(['group', 'seed']))
                    array = np.stack([part.sort_values('step')[measure].to_numpy() for _, part in groups])
                    precision.append({'kind': kind, 'state': state, 'cohort': cohort, 'measure': measure, 'mcse_sd': finite_call(lambda: az.mcse(array, method='sd')), 'mcse_q05': finite_call(lambda: az.mcse(array, method='quantile', prob=.05)), 'mcse_q95': finite_call(lambda: az.mcse(array, method='quantile', prob=.95))})
                    if kind == 'election':
                        index = [model['office'] for model in source['results'][state]['models']].index(measure)
                        for year, enacted in source['results'][state]['enacted_seats'].items():
                            tails.append({'state': state, 'cohort': cohort, 'election': measure, 'enacted_year': year, 'chain_order': [{'group': group, 'seed': int(seed)} for (group, seed), _ in groups], **tail_diagnostics(array, enacted[index])})
    value = {'scope': 'Saved postwarmup checkpoint series, not full-history frequency uncertainty. Adjacent event runs refer to successive saved checkpoints, which are 100 raw states apart. A constant indicator has unavailable uncertainty, rather than zero estimated error.', 'research_ready': False, 'precision': precision, 'enacted_score_frequency': tails}
    target.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
    records = []
    for row in precision:
        records.append({key: row[key] for key in ['kind', 'state', 'cohort', 'measure']} | {key: row[key]['value'] for key in ['mcse_sd', 'mcse_q05', 'mcse_q95']} | {key + '_status': row[key]['status'] for key in ['mcse_sd', 'mcse_q05', 'mcse_q95']})
    pd.DataFrame(records).to_csv(directory / 'additional_precision.csv', index=False)
    pd.DataFrame([{key: row[key] for key in ['state', 'cohort', 'election', 'enacted_year', 'threshold', 'events', 'observations', 'frequency']} | {'mcse_frequency': row['mcse_frequency']['value'], 'mcse_status': row['mcse_frequency']['status']} for row in tails]).to_csv(directory / 'enacted_frequency_precision.csv', index=False)
    print('Precision series:', len(precision), 'frequency series:', len(tails), 'unavailable frequency MCSE:', sum(item['mcse_frequency']['status'] != 'finite' for item in tails))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    run(parser.parse_args().directory)


if __name__ == '__main__':
    main()
