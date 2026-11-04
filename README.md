# Gerrymander Detector

**Status (November 2026):** I froze North Carolina's six chains at 23,000 states per chain under [`nc-baseline-23000`](https://github.com/httpsbina/gerrymander-detector/tree/nc-baseline-23000) and Texas's eight chains at 70,000 under [`texas-baseline-70000`](https://github.com/httpsbina/gerrymander-detector/tree/texas-baseline-70000). Every primary metric passes jointly and within each starting-map cohort. The [freeze rule](docs/freeze_rule.md), [frozen numbers](paper/results.json), and [paper outputs](paper/README.md) record the stopping criteria and reproduction commands.

I compare congressional maps with alternative plans sampled using GerryChain's ReCom algorithm. I conduct this research through the [PEAK Award](https://undergraduate.northeastern.edu/research/awards/peak-fellowships-overview/) at [Northeastern University](https://www.northeastern.edu/), advised by Dr. Eric Gerber, using data from the Redistricting Data Hub.

## Results

I ran three NC chains from the 2023 assignment and three from the 2025 assignment, using the same 2,681-unit Census-block-union geography for both. The geography retains all 236,638 blocks, population 10,439,388 and the Onslow split. Both starting maps have 3 Democratic-majority districts under the modeled 2024 presidential votes.

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

## Texas rebuild

I score PLANC2333 at Census-block resolution because its assignment splits precincts. The initial simulation baseline used 9,712 geographic units, 38 districts and a ±0.1% population bound; its 4,000-state chains gave the following presidential-vote comparison before continuation.

| Measure                                    | Initial 4,000-state baseline |
| ------------------------------------------ | ---------------------------: |
| PLANC2333 Democratic-majority districts    |                            8 |
| Sampled seat-count range after warmup      |                         8–17 |
| Mean sampled Democratic-majority districts |                      12.9562 |
| Retained states with 8 districts           |                   4 / 14,000 |

I verified that the four states have distinct partitions, at steps 2,253, 2,256, 2,257 and 2,258 of one chain. The [assignment check](deliverables/rebuild-campaign-2026-11-02/tail_assignment_check/assignment_verification.json) records that verification, and the [tail table](deliverables/rebuild-campaign-2026-11-02/enacted_tail_counts.csv) keeps counts by chain and sensitivity condition.

## Data and method

I join Census population, RDH election allocations and official assignments by block ID, checking coverage and statewide totals before constructing the geographic graph. I then check geometry, adjacency and district contiguity, and run ReCom with population bounds of ±0.1% for Texas and ±0.5% for NC. I keep election-model, population-bound and geography experiments separate; the precinct-based NC graph differs from the block-union graph by 47 edges.

The [source report](deliverables/rdh-research-audit-2026-11-02/README.md) records the input checks and election-source differences. The [initial campaign report](deliverables/rebuild-campaign-2026-11-02/README.md) covers 26 baseline and sensitivity chains before continuation. I retain the [earlier Texas analysis](docs/archive/texas-analysis-before-2026-11-rebuild.md) as a historical record.

## Reproducing

I use Python 3.12, GerryChain 0.3.2 and the [pinned research packages](requirements-research-macos-arm64-py312.txt). I run these commands from the repository root; the [state CLI guide](docs/state_cli.md) covers validation, simulation, continuation and audits. The manifests record the source-data and full-output paths, which are stored separately from the checkout.

```sh
.venv/science/bin/python main.py --texas --config configs/research_rebuild_2026-11-02.json
.venv/science/bin/python main.py --nc --config configs/research_rebuild_2026-11-02.json
.venv/science/bin/python -m unittest discover -s tests -v
```

I export both frozen analyses with `python -m paper.export`. The command writes [figures](paper/figures), [tables](paper/tables), [full-precision values](paper/results.json) and the state findings, using the registered NC23k and Texas70k freezes. The [docs index](docs/README.md) links the supporting records.

## Limitations

The primary convergence freezes are complete; MCSE and window-stability acceptance criteria still need scientific review. I use modeled presidential vote allocations and a sampler constrained by population and graph contiguity. I have not established uniform sampling over valid maps, and these constraints cover only part of the legal redistricting requirements. The source and campaign reports describe the remaining geographic and election-source uncertainties. I report tail counts as descriptive frequencies, including zero counts; they are not calibrated p-values or estimates of zero probability. The earlier Texas chain files are unavailable, so I cannot revalidate that historical analysis.

## References

DeFord, D., Duchin, M., and Solomon, J. (2021). [Recombination: A Family of Markov Chains for Redistricting](https://hdsr.mitpress.mit.edu/pub/1ds8ptxu). _Harvard Data Science Review_, 3(1).

Vehtari, A. et al. [Rank-normalization, folding, and localization: An improved R-hat for assessing convergence of MCMC](https://arxiv.org/abs/1903.08008).
