# Gerrymander Detector

**Status (November 2026):** North Carolina's six baseline chains pass all four primary convergence screens jointly and within both starting-map groups. I froze the numerical results at 23,000 states per chain under [`nc-baseline-23000`](https://github.com/httpsbina/gerrymander-detector/tree/nc-baseline-23000). Texas continues with four baseline chains and four independent dispersed-start chains. The [freeze rule](docs/freeze_rule.md), [frozen numbers](results.json), and [continuation guide](docs/continuation.md) record the stopping criteria and reproduction commands.

[![Python](https://img.shields.io/badge/Python-3.12-blue)](https://python.org)
[![GerryChain](https://img.shields.io/badge/GerryChain-0.3.2-green)](https://github.com/mggg/GerryChain)
[![Data](https://img.shields.io/badge/Data-Redistricting%20Data%20Hub-orange)](https://redistrictingdatahub.org)

I study how congressional maps compare with alternative plans sampled using GerryChain's ReCom algorithm. This is my [PEAK Award](https://undergraduate.northeastern.edu/research/awards/peak-fellowships-overview/) research at [Northeastern University](https://www.northeastern.edu/), advised by Dr. Eric Gerber.

## November 2026 results

I froze North Carolina at 23,000 states per chain; the Texas row below records the 15,000-state baseline audit. I keep later baseline and dispersed-cohort audits in the [continued-run records](deliverables/primary-freeze-2026-11-02/).

| Baseline group         | Chains × states | Seat R-hat | Bulk ESS | Tail ESS |
| ---------------------- | --------------: | ---------: | -------: | -------: |
| Texas, ±0.1%           |      4 × 15,000 |    1.00790 |    221.7 |    385.3 |
| NC, 2023 starting map  |      3 × 23,000 |    1.00367 |    954.0 |   1756.8 |
| NC, 2025 starting map  |      3 × 23,000 |    1.00185 |   1118.7 |   1543.3 |
| NC, both starting maps |      6 × 23,000 |    1.00268 |   2025.3 |   3267.9 |

I require R-hat below 1.01 and bulk/tail ESS at least 400 within each three-chain NC group and at least 600 jointly. All four NC metrics pass; Texas is still running, though. The [progress record](deliverables/primary-freeze-2026-11-02/progress.json) includes metric diagnostics and the seed/county disagreement comparison.

The [initial source-rebuild campaign](deliverables/rebuild-campaign-2026-11-02/README.md) contains the original 26-chain baseline and sensitivity runs. Those files remain separate from the continued baselines.

### Initial Texas seat comparison

PLANC2333 is scored at Census-block resolution using modeled 2024 presidential votes. The simulation baseline uses 9,712 geographic units, 38 districts and a ±0.1% population bound. The table below describes the initial campaign before continuation.

| Measure                                    | Initial 4,000-state baseline |
| ------------------------------------------ | ---------------------------: |
| PLANC2333 Democratic-majority districts    |                            8 |
| Sampled seat-count range after warmup      |                         8–17 |
| Mean sampled Democratic-majority districts |                      12.9562 |
| Retained states with 8 districts           |                   4 / 14,000 |

Those four states have distinct plan hashes and occur in one chain at steps 2,253, 2,256, 2,257 and 2,258. The [assignment check](deliverables/rebuild-campaign-2026-11-02/tail_assignment_check/assignment_verification.json) verifies the four partitions directly, and the [tail audit](deliverables/rebuild-campaign-2026-11-02/enacted_tail_counts.csv) records counts for every chain and sensitivity condition.

### North Carolina geography

The 2023 and 2025 assignments use the same 2,681-unit Census-block-union baseline, retaining all 236,638 blocks and population 10,439,388. Both maps score 3 Democratic-majority districts under the modeled presidential votes. The common geography includes the Onslow split. The precinct-based alternative differs by 47 graph edges and is analyzed as a separate sensitivity condition.

## Methods and data

I match Census population, RDH election allocations, and official assignments by block ID, then check coverage, totals, geometry, adjacency, and contiguity. I sample plans with ReCom under population and graph-contiguity constraints, using primary bounds of ±0.1% for Texas and ±0.5% for NC. I analyze independent chains and starting-map groups separately and jointly, with election-model, constraint, and geography comparisons kept as separate experiments.

The [source audit](deliverables/rdh-research-audit-2026-11-02/README.md) records provenance, election-total discrepancies, geometry construction and enacted-plan election sensitivity. The [campaign audit](deliverables/rebuild-campaign-2026-11-02/README.md) contains the results, commands and [scientific limitations](deliverables/rebuild-campaign-2026-11-02/README.md#limitations).

This analysis was conducted using data from the Redistricting Data Hub.

## Running the project

I use Python 3.12 and the pinned [research dependencies](requirements-research-macos-arm64-py312.txt). The [state CLI guide](docs/state_cli.md) covers validation, candidate construction, simulation, checkpoint continuation and audits. Source data and full simulation outputs are stored under the paths recorded in the manifests and are not bundled in the repository.

```sh
.venv/science/bin/python main.py --texas --config configs/research_rebuild_2026-11-02.json
.venv/science/bin/python main.py --nc --config configs/research_rebuild_2026-11-02.json
.venv/science/bin/python -m unittest discover -s tests -v
```

## Paper outputs

I regenerate the frozen analysis with `python -m paper.export`, which writes [figures](paper/figures), [tables](paper/tables), [full-precision numbers](paper/results.json), and a [one-page NC findings list](paper/nc_findings.md). The exporter reads the freeze registry, so Texas is included when its frozen outputs are registered. The [documentation index](docs/README.md) collects the workflow and data notes.

## Earlier analysis

The [historical Texas report](docs/archive/texas-analysis-before-2026-11-rebuild.md) preserves the earlier figures and reported 30,000-state results. It is superseded by the November 2026 campaign above.

## Limitations

I use modeled presidential vote allocations, while ReCom supplies the implemented sampling process and population/contiguity constraints. Uniform sampling and full legal compliance are outside the model. The source and campaign reports record the remaining geographic and election-source uncertainties. I treat tail counts as descriptive frequencies, including zero counts, and retain the earlier analysis as a historical record because its chain files are unavailable.

## References

DeFord, D., Duchin, M., and Solomon, J. (2021). [Recombination: A Family of Markov Chains for Redistricting](https://hdsr.mitpress.mit.edu/pub/1ds8ptxu). _Harvard Data Science Review_, 3(1).

Vehtari, A. et al. [Rank-normalization, folding, and localization: An improved R-hat for assessing convergence of MCMC](https://arxiv.org/abs/1903.08008).
