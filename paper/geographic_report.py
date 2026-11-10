"""Render the exploratory geographic clustering comparison from recorded scores."""

import argparse
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from paper.geographic_clustering import sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    directory = args.directory
    result = json.loads((directory / 'results.json').read_text())
    table = pd.read_csv(directory / 'scores.csv')
    fig, axes = plt.subplots(2, 3, figsize=(13, 7))
    names = {'silhouette': 'Silhouette (higher = more separated)', 'normalized_rms_radius': 'Normalized RMS radius (lower = tighter)', 'radial_cv': 'Radial CV (no general better direction)'}
    for row, state in enumerate(('tx', 'nc')):
        subset = table[(table.state == state) & (table.sample_size == 2048)]
        for col, (metric, title) in enumerate(names.items()):
            ax = axes[row, col]
            for group, values in subset[~subset.group.str.startswith('enacted')].groupby('group'):
                ax.hist(values[metric], bins=np.histogram_bin_edges(subset[~subset.group.str.startswith('enacted')][metric], bins=12), alpha=0.5, label=group.replace('_', ' '))
            for group, values in subset[subset.group.str.startswith('enacted')].groupby('group'):
                ax.axvline(values[metric].iloc[0], color='black' if group.endswith('2025') else 'crimson', linestyle='--', label=group.replace('_', ' '))
            ax.set_title(('Texas' if state == 'tx' else 'North Carolina') + '\n' + title, fontsize=10)
            ax.set_ylabel('Saved checkpoints')
            ax.legend(fontsize=6)
    fig.suptitle('Exploratory geography comparison: 2,048 population-sampled block locations')
    fig.tight_layout()
    fig.savefig(directory / 'geographic_comparison.png', dpi=180)
    plt.close(fig)
    lines = ['# Geographic clustering comparison', '', 'I compared the enacted maps with ten saved checkpoints from each frozen chain, using the same Census-block locations for every map within a state. Texas contributes 80 checkpoints and NC contributes 60; I used no election or party fields in these scores.', '', 'I sampled blocks with probability proportional to Census population, with replacement and seed 20261109, and represented each sampled location by its block centroid in EPSG:5070. I evaluated nested samples of 1,024 and 2,048 locations. Texas enacted assignments remain at block resolution, including blocks in split simulation units.', '', '| State and map | Silhouette | Simulated median | Normalized RMS radius | Simulated median |', '| --- | ---: | ---: | ---: | ---: |']
    for state, year in [('tx', 2025), ('nc', 2023), ('nc', 2025)]:
        found = {r['metric']: r for r in result['comparisons'] if r['state'] == state and r['enacted'] == f'enacted_{year}' and r['sample_size'] == 2048 and r['cohort'] == 'joint'}
        s, d = found['silhouette'], found['normalized_rms_radius']
        lines.append(f"| {state.upper()} {year} | {s['value']:.4f} | {s['median']:.4f} | {d['value']:.4f} | {d['median']:.4f} |")
    lines.extend(['', 'At both sample sizes, each enacted map has a lower silhouette and a larger normalized radius than every sampled checkpoint in its state, including comparisons within each starting-map cohort. These are observed ranks in this pilot.', '', '## Measures', '', 'I retain silhouette and normalized RMS radius as the two clustering measures for further evaluation. Silhouette compares mean within-district distance with mean distance to the nearest other district; normalized RMS radius divides the population-sample root-mean-square distance to district centers by statewide RMS distance to the statewide center. The latter is a within-state scale normalization, rather than a correction for individual district area. Their Spearman correlations among the 2,048-location checkpoint scores are -0.485 in Texas and -0.709 in NC, so they overlap without giving identical rankings.', '', 'I also calculated the population-weighted mean of district radial coefficients of variation, using population SD divided by mean distance from each sampled district center. Texas moves from the 80th to the 50th percentile when the location sample doubles, while both NC maps remain below every pilot checkpoint. A narrow ring can have a low radial CV despite poor compactness, so I keep this measure in the exploratory results rather than treating low CV as better geography.', '', 'Polsby-Popper, county splits and perimeter measures are not computed in this report. A boundary measure would add information that these distance scores do not capture; I need a consistent boundary-resolution comparison before selecting a third measure, particularly because Texas simulation units and its enacted districts have different boundaries.', '', '## Limitations', '', 'This is a geographic pilot using 140 correlated checkpoint observations and one nested random location sample per state, not a full-ensemble percentile estimate. Doubling that sample checks sensitivity to sample size but does not quantify sampling uncertainty. Block centroids approximate resident locations, projected Euclidean distance differs from travel distance, and statewide averages can hide individual districts. Zero-population blocks remain in the source geography but have no mass in a resident-weighted score. The chains were screened for the original four metrics; convergence and Monte Carlo error for these new geographic metrics have not been established. The reference ensemble retains its existing boundary and population constraints and is not a uniform sample of all possible maps. These scores measure geographic unusualness within that reference, rather than partisan intent or legal compliance.', '', '## Reproducing', '', '```sh', 'OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 python -m paper.geographic_clustering --source-root SOURCE_CHECKOUT --output-dir NEW_OUTPUT_DIRECTORY', 'MPLCONFIGDIR=.venv/matplotlib python -m paper.geographic_report NEW_OUTPUT_DIRECTORY', 'python -m unittest discover -s tests -v', '```', '', 'SOURCE_CHECKOUT is the checkout containing the frozen data and checkpoints; the output directory must be new. Input hashes, the checkpoint selection rule and metric values are in results.json; scores.csv records every checkpoint and comparisons.csv includes separate starting-map cohorts. The block samples are recorded in tx_sample.csv and nc_sample.csv. I use the standard [silhouette definition](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.silhouette_score.html).'])
    (directory / 'README.md').write_text('\n'.join(lines) + '\n')
    paths = [directory / name for name in ('geographic_comparison.png', 'README.md')]
    if any(not path.is_file() for path in paths):
        raise ValueError('Missing report output')


if __name__ == '__main__':
    main()
