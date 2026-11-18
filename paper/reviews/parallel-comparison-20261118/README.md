# Parallel comparison for Gerber

I compared geographic structure and modeled electoral outcomes on the same saved maps. I used all available 100-state checkpoints after the existing 500-state warmup, while retaining the full chain histories as a separate electoral summary.

## Full histories and saved checkpoints

| State   | Scope                        | Observations | Enacted score | Mean score | At or below enacted |
| ------- | ---------------------------- | -----------: | ------------: | ---------: | ------------------: |
| TX 2025 | full retained history        |      556,000 |             8 |    12.8627 |                  76 |
| TX 2025 | saved postwarmup checkpoints |        5,560 |             8 |    12.8635 |                   2 |
| NC 2023 | full retained history        |      135,000 |             3 |     5.3210 |               1,020 |
| NC 2023 | saved postwarmup checkpoints |        1,350 |             3 |     5.3504 |                   7 |
| NC 2025 | full retained history        |      135,000 |             3 |     5.3210 |               1,020 |
| NC 2025 | saved postwarmup checkpoints |        1,350 |             3 |     5.3504 |                   7 |

The counts describe states, including revisits. I report full histories and saved checkpoints separately. The same-map figures use saved checkpoints; their smaller tail counts do not replace the full-history findings.

## Mean distance and variation

| Map     | Mean distance, km |  SD, km |     CV | Inverse CV |
| ------- | ----------------: | ------: | -----: | ---------: |
| TX 2025 |           52.8458 | 65.7667 | 1.2445 |     0.8035 |
| NC 2023 |           41.1857 | 27.9337 | 0.6782 |     1.4744 |
| NC 2025 |           41.8045 | 28.2722 | 0.6763 |     1.4786 |

CV is the population-weighted SD of distance divided by its mean, and inverse CV is the reciprocal per-map score. Mean distance and SD can both increase while their ratio changes little. Low CV means more similar distances, rather than short distances; I retain the original distance scale alongside the ratios.

## Parallel outcomes

The geographic metrics are calculated without votes. I then pair them with electoral scores by state, starting-map cohort, seed, step and plan hash, and report descriptive associations within each chain and cohort as well as jointly. The heatmaps use the full frozen checkpoint set for every existing election, including the additional Texas checkpoints beyond the earlier 45,000-state comparison.

full_election_responsiveness.png shows the observed range and median for each election, with both NC enacted plans marked. The points are different 2024 statewide contests, rather than a fitted swing curve. all_election_summary.csv records every enacted score, mean, median, range and count at or below the enacted score.

## Diagnostics

diagnostics.csv records every distance and election screen by starting-map cohort and jointly, with the existing R-hat and ESS reference values. results.json and paired_election_results.json retain warmup and half-history sensitivity. Several new distance measures miss the reference screens, so the original electoral freezes do not certify the new geographic quantities.

The fixed-center projection check uses all block locations on 143 preselected assignments. Switching from projected to GRS80 ellipsoidal distance changes mean distance by at most 0.263% and CV by at most 0.411% in that pilot; this does not re-optimize centers on the ellipsoid.

additional_precision.json retains MCSE for SD and the 5th and 95th percentiles, plus enacted-score indicator diagnostics. Frequency MCSE is unavailable in 34 of 117 series because the indicators are constant. These cases remain recorded.

## Limitations

The reference ensemble retains its existing constraints and simulation units. Texas enacted lines can split units where sampled maps cannot, and the original Texas sampler geography retains its documented overlap warnings. Population distances use 2020 Census block centroids, while election scores use modeled block allocations of 2024 returns; these are not actual 2026 congressional results. Some geographic values lie outside the observed reference range, so I do not extrapolate a geography-adjusted electoral comparison. Correlations do not establish independence or causation, and serial dependence rules out treating the observations as IID for p-values. Finite MCSE values are not precision guarantees when convergence fails. Tail frequencies are descriptive; a constant event indicator has unavailable uncertainty rather than zero error, and the counts are not calibrated p-values. The original freezes remain unchanged.

## Reproducing

The exact commands and checks are in execution.json and verification.json. The pinned environment is preserved. Full election assignment fingerprints are checked against the original graph, and an independent bincount tally checks every plan and election. Existing election scores are retained and compared with the expanded scoring. The read-only assignment audit is separate from replay or continuation certification.

The methods are in [parallel_comparison.md](../../../docs/parallel_comparison.md).
