# Gerrymander Detector

**Status (November 2026):** I rebuilt the Texas and North Carolina analyses from Redistricting Data Hub sources. The new chains do not yet meet the convergence thresholds used in the audit: R-hat below 1.01 and bulk/tail ESS of at least `max(400, 100 × chains)`, with a floor of 600 for six-chain NC groups. The earlier chain files are no longer available, so I have not been able to revalidate the historical results. The Texas rebuild produced four distinct sampled plans with 8 Democratic-majority districts, so the earlier claim that PLANC2333 falls below every sampled plan does not hold for the new ensemble. Full diagnostics are in the [campaign audit](deliverables/rebuild-campaign-2026-11-02/README.md).

[![Python](https://img.shields.io/badge/Python-3.12-blue)](https://python.org)
[![GerryChain](https://img.shields.io/badge/GerryChain-0.3.2-green)](https://github.com/mggg/GerryChain)
[![Data](https://img.shields.io/badge/Data-Redistricting%20Data%20Hub-orange)](https://redistrictingdatahub.org)

I study how congressional maps compare with alternative plans sampled using GerryChain's ReCom algorithm. This is my [PEAK Award](https://undergraduate.northeastern.edu/research/awards/peak-fellowships-overview/) research at [Northeastern University](https://www.northeastern.edu/), advised by Dr. Eric Gerber.

## November 2026 results

The campaign contains 26 chains and 122,000 recorded states across baseline, geography and population-tolerance conditions. With 500 warmup states per chain, 109,000 states remain for the primary diagnostic view. Conditions are analyzed separately.

| Baseline group         | Chains × states | Seat R-hat | Bulk ESS | Tail ESS |
| ---------------------- | --------------: | ---------: | -------: | -------: |
| Texas, ±0.1%           |       4 × 4,000 |    1.03644 |    100.9 |    145.5 |
| NC, 2023 starting map  |       3 × 5,000 |    1.00924 |    210.3 |    553.4 |
| NC, 2025 starting map  |       3 × 5,000 |    1.01485 |    231.3 |    292.6 |
| NC, both starting maps |       6 × 5,000 |    1.01135 |    451.8 |    758.1 |

All 44 primary metric/group combinations fall below their bulk-ESS screen. The audit also reports tail ESS, Monte Carlo errors, trace/rank plots, autocorrelation, window stability, warmup sensitivity and starting-map sensitivity.

### Texas seat comparison

PLANC2333 is scored at Census-block resolution using modeled 2024 presidential votes. The simulation baseline uses 9,712 geographic units, 38 districts and a ±0.1% population bound.

| Measure                                    | November 2026 baseline |
| ------------------------------------------ | ---------------------: |
| PLANC2333 Democratic-majority districts    |                      8 |
| Sampled seat-count range after warmup      |                   8–17 |
| Mean sampled Democratic-majority districts |                12.9562 |
| Retained states with 8 districts           |             4 / 14,000 |

Those four states have distinct plan hashes and occur in one chain at steps 2,253, 2,256, 2,257 and 2,258. The [tail audit](deliverables/rebuild-campaign-2026-11-02/enacted_tail_counts.csv) records counts for every chain and sensitivity condition.

### North Carolina geography

The 2023 and 2025 assignments use the same 2,681-unit Census-block-union baseline, retaining all 236,638 blocks and population 10,439,388. Both maps score 3 Democratic-majority districts under the modeled presidential votes. The common geography includes the Onslow split. The precinct-based alternative differs by 47 graph edges and is analyzed as a separate sensitivity condition.

## Methods and data

1. Match Census population, RDH election allocations and official block-to-district assignments by unique block ID.
2. Audit coverage, totals, geometry, overlaps, adjacency and district contiguity.
3. Sample plans using ReCom with population and graph-contiguity constraints. The primary bounds are ±0.1% for Texas and ±0.5% for NC.
4. Analyze independent-seed chains and NC starting-map groups using the recorded configurations.
5. Compare election models, population constraints and geographic constructions.

The [source audit](deliverables/rdh-research-audit-2026-11-02/README.md) records provenance, election-total discrepancies, geometry construction and enacted-plan election sensitivity. The [campaign audit](deliverables/rebuild-campaign-2026-11-02/README.md) contains the results, commands and [scientific limitations](deliverables/rebuild-campaign-2026-11-02/README.md#limitations).

This analysis was conducted using data from the Redistricting Data Hub.

## Running the project

Use Python 3.12 and the pinned [research dependencies](requirements-research-macos-arm64-py312.txt). The [state CLI guide](docs/state_cli.md) covers validation, candidate construction, simulation, checkpoint continuation and audits. Source data and full simulation outputs are stored under the paths recorded in the manifests and are not bundled in the repository.

```sh
.venv/science/bin/python main.py --texas --config configs/research_rebuild_2026-11-02.json
.venv/science/bin/python main.py --nc --config configs/research_rebuild_2026-11-02.json
.venv/science/bin/python -m unittest discover -s tests -v
```

## Earlier analysis

The [historical Texas report](docs/archive/texas-analysis-before-2026-11-rebuild.md) preserves the earlier figures and reported 30,000-state results. It is superseded by the November 2026 campaign above.

## References

DeFord, D., Duchin, M., and Solomon, J. (2021). [Recombination: A Family of Markov Chains for Redistricting](https://hdsr.mitpress.mit.edu/pub/1ds8ptxu). _Harvard Data Science Review_, 3(1).

Vehtari, A. et al. [Rank-normalization, folding, and localization: An improved R-hat for assessing convergence of MCMC](https://arxiv.org/abs/1903.08008).
