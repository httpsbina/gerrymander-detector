# Gerrymander Detector

**Status (November 2026):** I froze North Carolina's six chains at 23,000 states per chain under [`nc-baseline-23000`](https://github.com/httpsbina/gerrymander-detector/tree/nc-baseline-23000) and Texas's eight chains at 70,000 under [`texas-baseline-70000`](https://github.com/httpsbina/gerrymander-detector/tree/texas-baseline-70000). Every primary metric passes jointly and within each starting-map cohort. The [freeze rule](docs/freeze_rule.md), [frozen numbers](paper/results.json), and [paper outputs](paper/README.md) record the stopping criteria and reproduction commands.

[![Python](https://img.shields.io/badge/Python-3.12-blue)](https://python.org)
[![GerryChain](https://img.shields.io/badge/GerryChain-0.3.2-green)](https://github.com/mggg/GerryChain)
[![Data](https://img.shields.io/badge/Data-Redistricting%20Data%20Hub-orange)](https://redistrictingdatahub.org)

I study how congressional maps compare with alternative plans sampled using GerryChain's ReCom algorithm. This is my [PEAK Award](https://undergraduate.northeastern.edu/research/awards/peak-fellowships-overview/) research at [Northeastern University](https://www.northeastern.edu/), advised by Dr. Eric Gerber.

## November 2026 results

I froze both states after all four primary metrics passed at the same complete chain length within each cohort and jointly. The table shows the seat-count diagnostics; the [frozen paper results](paper/results.json) contain every metric.

| Starting group        | Chains × states | Seat R-hat | Bulk ESS | Tail ESS |
| --------------------- | --------------: | ---------: | -------: | -------: |
| Texas, baseline       |      4 × 70,000 |    1.00544 |   1463.0 |   2429.7 |
| Texas, dispersed      |      4 × 70,000 |    1.00256 |   1136.5 |   2606.0 |
| Texas, joint          |      8 × 70,000 |    1.00385 |   2628.3 |   5024.8 |
| NC, 2023 starting map |      3 × 23,000 |    1.00367 |    954.0 |   1756.8 |
| NC, 2025 starting map |      3 × 23,000 |    1.00185 |   1118.7 |   1543.3 |
| NC, joint             |      6 × 23,000 |    1.00268 |   2025.3 |   3267.9 |

I use R-hat below 1.01 and bulk/tail ESS of at least 400 within each cohort, 600 for joint NC and 800 for joint Texas. I retained all earlier states, seeds and starting maps.

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

I regenerate the frozen analysis with `python -m paper.export`, which writes [figures](paper/figures), [tables](paper/tables), [full-precision numbers](paper/results.json), and a [one-page NC findings list](paper/nc_findings.md). Both states are registered in the frozen export. The [documentation index](docs/README.md) collects the workflow and data notes.

## Earlier analysis

The [historical Texas report](docs/archive/texas-analysis-before-2026-11-rebuild.md) preserves the earlier figures and reported 30,000-state results. It is superseded by the November 2026 campaign above.

## Limitations

The primary convergence freeze is complete; MCSE and window-stability acceptance criteria still need scientific review. I use modeled presidential vote allocations, while ReCom supplies the implemented sampling process and population/contiguity constraints. Uniform sampling and full legal compliance are outside the model. The source and campaign reports record the remaining geographic and election-source uncertainties. I treat tail counts as descriptive frequencies, including zero counts, and retain the earlier analysis as a historical record because its chain files are unavailable.

## References

DeFord, D., Duchin, M., and Solomon, J. (2021). [Recombination: A Family of Markov Chains for Redistricting](https://hdsr.mitpress.mit.edu/pub/1ds8ptxu). _Harvard Data Science Review_, 3(1).

Vehtari, A. et al. [Rank-normalization, folding, and localization: An improved R-hat for assessing convergence of MCMC](https://arxiv.org/abs/1903.08008).
