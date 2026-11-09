# Frozen-run precision and stability review

I reviewed the frozen NC23k and Texas70k histories, retaining the existing 500-state warmup, all chains and all later observations. I reproduced each recorded mean MCSE with the pinned ArviZ version, checked the stored first/last 1,000-state comparisons, and added post-warmup half comparisons and direct seat-tail indicators. I have left the new acceptance decisions pending; the freezes and primary screens are unchanged.

## Mean precision

Each cell gives the estimated mean followed by its MCSE in parentheses. Efficiency gap and median minus mean use percentage points; seats and cut edges keep their original units. The complete SD and quantile MCSE records are in `summary.csv` and `results.json`.

### North Carolina

| Metric                               | nc_block_union_2023 | nc_block_union_2025 |               joint |
| ------------------------------------ | ------------------: | ------------------: | ------------------: |
| Democratic seats, seats              |   5.34428 (0.02645) |   5.29778 (0.02491) |   5.32103 (0.01836) |
| Efficiency gap, percentage points    |  -8.51553 (0.19016) |  -8.86694 (0.17990) |  -8.69123 (0.13251) |
| Cut edges, edges                     | 729.58361 (1.27205) | 732.25650 (1.25888) | 730.92006 (0.91194) |
| Median minus mean, percentage points |  -1.78152 (0.03891) |  -1.77610 (0.03424) |  -1.77881 (0.02590) |

### Texas

| Metric                               |           tx_rebuild |         tx_dispersed |                joint |
| ------------------------------------ | -------------------: | -------------------: | -------------------: |
| Democratic seats, seats              |   12.88051 (0.03348) |   12.84486 (0.03786) |   12.86269 (0.02494) |
| Efficiency gap, percentage points    |   -5.21091 (0.08820) |   -5.30674 (0.09880) |   -5.25883 (0.06513) |
| Cut edges, edges                     | 2668.96074 (3.18020) | 2672.96281 (2.98588) | 2670.96178 (2.20107) |
| Median minus mean, percentage points |    0.90544 (0.03921) |    0.98835 (0.03888) |    0.94689 (0.02808) |

I use mean-specific MCSE from ArviZ rather than reconstructing it from rank-normalized bulk ESS. The pinned implementation uses the sample SD divided by the square root of mean-specific ESS. MCSE measures simulation error in an estimated expectation; the spread of sampled plans is a separate quantity. The [diagnostic paper, sections 3.2 and 4.1](https://arxiv.org/html/1903.08008v5), explains that distinction.

## Starting-map comparison

I subtract the first cohort's mean from the second cohort's mean: NC 2025 minus NC 2023, and Texas dispersed minus baseline. I combine their MCSEs by the square root of the sum of squares because the chain groups use independent seeds. The resulting ratio is a descriptive precision comparison, with no rejection threshold applied.

| State | Metric            | Cohort difference | Combined MCSE | Difference / MCSE |
| ----- | ----------------- | ----------------: | ------------: | ----------------: |
| nc    | Democratic seats  |          -0.04650 |       0.03633 |            -1.280 |
| nc    | Efficiency gap    |          -0.35141 |       0.26177 |            -1.342 |
| nc    | Cut edges         |           2.67289 |       1.78966 |             1.494 |
| nc    | Median minus mean |           0.00542 |       0.05183 |             0.105 |
| texas | Democratic seats  |          -0.03564 |       0.05054 |            -0.705 |
| texas | Efficiency gap    |          -0.09584 |       0.13244 |            -0.724 |
| texas | Cut edges         |           4.00207 |       4.36224 |             0.917 |
| texas | Median minus mean |           0.08291 |       0.05522 |             1.501 |

## Window and warmup comparisons

I split each post-warmup history into contiguous halves and retain every observation. The table reports the joint second-half mean minus first-half mean, alongside each half's MCSE. The two halves belong to the same chains, so I report their MCSEs separately and do not use an independence-based test of their difference. `halves.csv` includes both cohorts as well as the joint group, and `chains.csv` retains every chain's half shift and the frozen first/last 1,000-state shift.

| State | Metric            | Half shift | First-half MCSE | Second-half MCSE | Largest individual-chain half shift |  Seed |
| ----- | ----------------- | ---------: | --------------: | ---------------: | ----------------------------------: | ----: |
| nc    | Democratic seats  |    0.08446 |         0.02547 |          0.02592 |                             0.18044 |   909 |
| nc    | Efficiency gap    |    0.60533 |         0.18341 |          0.18674 |                             1.24538 |   909 |
| nc    | Cut edges         |   -1.32480 |         1.18773 |          1.32399 |                            -8.00169 |   909 |
| nc    | Median minus mean |   -0.02867 |         0.03345 |          0.03962 |                            -0.13420 |   707 |
| texas | Democratic seats  |   -0.00176 |         0.03747 |          0.03186 |                             0.32406 |  2227 |
| texas | Efficiency gap    |    0.04275 |         0.09847 |          0.08458 |                             0.92411 |  2227 |
| texas | Cut edges         |    1.33671 |         3.23549 |          3.28119 |                            26.76302 |  2227 |
| texas | Median minus mean |   -0.03728 |         0.04138 |          0.03644 |                             0.23316 | 10007 |

I also compare means after each recorded warmup choice with the registered 500-state result. The table gives the largest absolute mean shift among those choices; the full means and 5th/95th percentiles are in `warmups.csv`.

| State | Metric            | First cohort | Second cohort |   Joint |
| ----- | ----------------- | -----------: | ------------: | ------: |
| nc    | Democratic seats  |      0.00580 |       0.00536 | 0.00473 |
| nc    | Efficiency gap    |      0.04280 |       0.03824 | 0.03600 |
| nc    | Cut edges         |      0.79511 |       0.15712 | 0.47611 |
| nc    | Median minus mean |      0.00718 |       0.01408 | 0.01063 |
| texas | Democratic seats  |      0.00364 |       0.00240 | 0.00149 |
| texas | Efficiency gap    |      0.01261 |       0.00855 | 0.00577 |
| texas | Cut edges         |      0.94948 |       0.37987 | 0.66467 |
| texas | Median minus mean |      0.00926 |       0.00041 | 0.00453 |

The two running-mean figures use every stored audit window, weighted by its number of states. I draw each chain separately and mark its cohort's full retained-history mean with a dashed line. This keeps opposite chain movements visible when the joint mean changes little.

## Seat-tail precision

The recorded seat 5th/95th quantile MCSEs are zero. In the [quantile method, section 4.4](https://arxiv.org/html/1903.08008v5), uncertainty in a quantile's rank is mapped back to observed values; both endpoints can land on the same integer seat count. I therefore reviewed the separate binary event of scoring at or below each enacted presidential seat count.

| State | Group               | Score threshold | Events / retained states | Contiguous event runs | Frequency, % | MCSE, percentage points | Indicator R-hat |
| ----- | ------------------- | --------------: | ------------------------ | --------------------: | -----------: | ----------------------: | --------------: |
| nc    | nc_block_union_2023 |               3 | 394 / 67500              |                    80 |     0.583704 |                0.094664 |        1.000390 |
| nc    | nc_block_union_2025 |               3 | 626 / 67500              |                   102 |     0.927407 |                0.148722 |        1.000415 |
| nc    | joint               |               3 | 1020 / 135000            |                   182 |     0.755556 |                0.089210 |        1.000580 |
| texas | tx_rebuild          |               8 | 41 / 278000              |                     9 |     0.014748 |                0.007093 |        1.000210 |
| texas | tx_dispersed        |               8 | 35 / 278000              |                     6 |     0.012590 |                0.006301 |        1.000118 |
| texas | joint               |               8 | 76 / 556000              |                    15 |     0.013669 |                0.004744 |        1.000156 |

I estimate a relative MCSE of 11.81% for the joint nc tail frequency. Its 1020 event states occur in 182 contiguous runs, which I keep as descriptive episode counts.

I estimate a relative MCSE of 34.71% for the joint texas tail frequency. Its 76 event states occur in 15 contiguous runs, which I keep as descriptive episode counts.

## Decisions for review

I need to choose the paper's estimands and acceptable Monte Carlo error in their own units with Dr. Gerber, including whether the rare-event frequency is a numerical finding or only a descriptive count. I also need an agreed way to assess the observed window shifts and cohort differences against that precision budget. I have not assigned new tolerances or marked these comparisons as accepted. Any acceptance criteria will be recorded before they are used, with the existing freezes kept as the historical record.

## Reproducing

```sh
nice -n 15 env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 MPLCONFIGDIR="$PWD/.venv/matplotlib" .venv/science/bin/python -m paper.review_precision --source-root . --output-dir paper/reviews/NEW_REVIEW_DIRECTORY
nice -n 15 env MPLCONFIGDIR="$PWD/.venv/matplotlib" .venv/science/bin/python -m paper.precision_report --results paper/reviews/NEW_REVIEW_DIRECTORY/results.json
```

`results.json` records the full values, software versions, frozen-input checksums and diagnostic availability. The CSVs retain every metric, cohort and chain. `artifacts.json` records the output checksums. The MCSE definitions also follow the [mean](https://mc-stan.org/posterior/reference/mcse_mean.html) and [quantile](https://mc-stan.org/posterior/reference/mcse_quantile.html) estimands documented by the posterior package; all numerical calculations here use the pinned ArviZ implementation.

## Limitations

I use finite, autocorrelated simulations under the recorded ReCom constraints and modeled block votes. MCSE conditions on the sampled regime and does not include data/model uncertainty or undetected nonstationarity. Rare-event indicator R-hat can remain close to one with sparse events; a chain with no events gives limited information about unseen tails. Contiguous event runs are dependent observations, and zero observed events leave nonzero probabilities possible. These tail frequencies describe the implemented ensemble and are not calibrated p-values. The within-chain half comparisons are descriptive, and the stored NC windows include a shorter final window. This review leaves MCSE and stability acceptance pending, together with the earlier geographic, sampling-distribution and legal-model limitations.
