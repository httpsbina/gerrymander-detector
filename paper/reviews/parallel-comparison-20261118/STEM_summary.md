# Technical summary

I calculate pooled population-weighted radial mean mu and population SD sigma from every Census block centroid, then retain CV = sigma / mu and inverse CV = mu / sigma. I also retain the population-weighted mean of district CVs, which differs from pooled CV. The reciprocal score does not add independent evidence.

I pair every geographic and electoral record by cohort, seed, recorded step and plan hash. The primary comparison uses every saved 100-state checkpoint after warmup 500. Full-history seat summaries use every retained CSV state and remain separately labelled. The complete election set includes all locally available statewide contests selected by the existing model.

For every new distance quantity and election seat series, I retain rank-normalized split R-hat, bulk and tail ESS, mean MCSE, half-history comparisons and warmups 0, 250, 500 and 1,000. Every unavailable diagnostic remains recorded. Associations are descriptive Spearman coefficients with per-chain and starting-map-group comparisons, without IID significance tests.

## New distance diagnostics

| State | Measure           | Joint R-hat | Bulk ESS | Tail ESS |
| ----- | ----------------- | ----------: | -------: | -------: |
| NC    | Mean distance, km |      1.0067 |    516.4 |    788.4 |
| NC    | Distance SD, km   |      1.0024 |    807.9 |   1175.6 |
| NC    | Pooled radial CV  |      1.0026 |    744.9 |    967.2 |
| NC    | Inverse pooled CV |      1.0026 |    744.9 |    967.2 |
| NC    | Mean district CV  |      1.0056 |    571.0 |    901.5 |
| TX    | Mean distance, km |      1.0506 |    121.4 |    805.9 |
| TX    | Distance SD, km   |      1.0348 |    214.4 |    678.8 |
| TX    | Pooled radial CV  |      1.0197 |    628.8 |    609.4 |
| TX    | Inverse pooled CV |      1.0190 |    628.8 |    609.4 |
| TX    | Mean district CV  |      1.0156 |    467.6 |   2112.1 |

## Limitations

Several distance metrics fail existing reference screens, and the input geometry and model limitations remain. The observed geometric support does not justify extrapolating a conditional electoral comparison to every enacted score. The raw and expanded election comparisons use existing data only; no chain, constraint, threshold or frozen output changes.
