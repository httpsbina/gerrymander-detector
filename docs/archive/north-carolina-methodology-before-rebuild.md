# Earlier North Carolina study

I compared the 2023 and 2025 assignments on a common geography using modeled 2024 presidential votes before the source rebuild. I retain that run here; the [current NC analysis](../north_carolina_data.md) uses the frozen block-union baseline.

## Inputs and runs

| Input                                            | Recorded value |
| ------------------------------------------------ | -------------: |
| Common geographic units                          |          2,681 |
| Adjacency edges                                  |          7,583 |
| Congressional districts                          |             14 |
| 2020 population                                  |     10,439,388 |
| Modeled Harris votes                             |      2,713,609 |
| Modeled Trump votes                              |      2,896,942 |
| Harris-majority districts in either starting map |              3 |

I ran six ReCom chains from the 2023 and 2025 assignments on the same graph, using seeds 707, 808 and 909, population tolerance ±0.5% and `node_repeats=2`. Each chain recorded 5,000 states, giving 30,000 overall and 27,000 after 500 warmup states per chain. The starting assignments initialize the same intended ReCom process.

## Recorded results

| Joint metric     |  R-hat | Bulk ESS |
| ---------------- | -----: | -------: |
| Democratic seats | 1.0349 |    199.3 |
| Efficiency gap   | 1.0367 |    202.0 |
| Cut edges        | 1.0103 |    494.1 |

I observed autocorrelation and differences between trajectories, which remained in the 2,000- and 3,000-state warmup views.

I also ran two feasibility pilots at population tolerance ±0.1%:

| Starting assignment | Recorded states | Unique exact plans | Maximum deviation |
| ------------------- | --------------: | -----------------: | ----------------: |
| 2023                |             100 |                 99 |         0.099297% |
| 2025                |             100 |                 98 |         0.099853% |

For the enacted assignments, I shifted district-level Harris two-party share uniformly from −3 to +3 percentage points. The 2023 assignment moves from 3 to 4 Harris-majority districts at +2 points, with district 1 changing winner; the 2025 assignment remains at 3 through +3 points.

## Reproducing

I used these entry points from the repository root after preparing the environment and local inputs:

```sh
python src/analysis/analyze_nc_common_chains.py
python src/analysis/analyze_nc_vote_sensitivity.py
python src/analysis/make_nc_figures.py
```

The scripts analyze existing chains and write CSVs and PNGs under `outputs/analysis/`. I keep raw and processed data, checkpoints and those analysis outputs outside regular Git commits.

## Limitations

This earlier run did not resolve convergence, and consecutive states are correlated. I use modeled Census-block election allocations, with population and contiguity constraints that cover only part of the legal requirements; I have not established uniform sampling. The stricter pilots contain only 100 states each, and uniform vote swings leave independent-election sensitivity unanswered.
