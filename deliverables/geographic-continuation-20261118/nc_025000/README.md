# NC geographic continuation at 25,000 states

I extended all six existing NC chains to 25,000 states each, while preserving the 23,000-state freeze. The new geographic screens still fail, so I continue the same chains with unchanged thresholds and warmup.

## Geographic screens

Each cell reports R-hat / bulk ESS / tail ESS. I use R-hat below 1.01, ESS at least 400 within each three-chain cohort and 600 jointly.

| Measurement                 | Joint                    | 2023 starts            | 2025 starts            |
| --------------------------- | ------------------------ | ---------------------- | ---------------------- |
| silhouette                  | 1.0015 / 716.2 / 1102.2  | 1.0027 / 387.8 / 588.7 | 1.0016 / 318.9 / 551.8 |
| normalized_rms_radius       | 1.0051 / 658.0 / 972.2   | 1.0114 / 303.3 / 368.8 | 1.0016 / 312.3 / 510.1 |
| mean_polsby_popper          | 1.0020 / 1275.1 / 1360.0 | 1.0015 / 629.9 / 734.5 | 1.0053 / 609.6 / 629.3 |
| mean_distance_km            | 1.0065 / 554.2 / 862.7   | 1.0145 / 217.7 / 386.2 | 1.0039 / 269.1 / 456.0 |
| sd_distance_km              | 1.0025 / 914.3 / 1303.5  | 1.0028 / 496.6 / 514.0 | 1.0028 / 434.0 / 602.4 |
| distance_cv                 | 1.0033 / 790.4 / 1069.4  | 1.0014 / 511.0 / 679.5 | 1.0062 / 343.0 / 410.0 |
| inverse_distance_cv         | 1.0033 / 790.4 / 1069.4  | 1.0014 / 511.0 / 679.5 | 1.0062 / 343.0 / 410.0 |
| mean_district_cv            | 1.0035 / 606.0 / 1021.2  | 1.0113 / 290.7 / 624.2 | 0.9992 / 305.3 / 454.4 |
| internal_boundary_km        | 1.0009 / 1250.2 / 1354.8 | 1.0013 / 630.9 / 629.5 | 1.0026 / 629.4 / 735.3 |
| common_cut_edges            | 1.0012 / 999.1 / 1359.5  | 1.0056 / 592.3 / 735.7 | 0.9984 / 395.9 / 625.7 |
| density_weighted_boundary   | 1.0036 / 1087.6 / 1240.5 | 1.0090 / 610.0 / 578.0 | 0.9983 / 474.1 / 698.1 |
| area_normalized_rms_radius  | 1.0031 / 1211.3 / 1396.4 | 0.9987 / 590.4 / 669.9 | 1.0096 / 635.0 / 696.8 |
| area_weighted_polsby_popper | 1.0022 / 1363.9 / 1451.9 | 1.0048 / 647.5 / 623.0 | 1.0002 / 701.9 / 695.8 |
| median_polsby_popper        | 1.0026 / 1315.5 / 1447.3 | 1.0006 / 680.6 / 748.2 | 1.0057 / 623.0 / 734.9 |

All geographic diagnostic calculations returned finite values, including the existing warmup sensitivity grid and mean, SD and quantile Monte Carlo errors. The original four primary numerical screens also pass for both cohorts and jointly.

## Decreasing ESS

| Cohort              | Measurement           | Diagnostic | At 23,000 | At 25,000 |
| ------------------- | --------------------- | ---------- | --------- | --------- |
| nc_block_union_2023 | normalized_rms_radius | bulk_ess   | 316.0     | 303.3     |
| nc_block_union_2023 | normalized_rms_radius | tail_ess   | 386.9     | 368.8     |
| nc_block_union_2023 | mean_distance_km      | bulk_ess   | 218.7     | 217.7     |
| nc_block_union_2023 | mean_distance_km      | tail_ess   | 418.9     | 386.2     |
| nc_block_union_2023 | mean_district_cv      | bulk_ess   | 308.7     | 290.7     |

## Records

The complete-boundary backup contains 8,463 verified files; its remote SHA-256 matches `c528779870a1004eb9ae3ce6534ebd27602d9c85e4dbecdc58b23539943a7c0b`, and the release remains draft. It covers NC at 25,000 and Texas at 72,000 states per chain. The run rules and preflight are in the parent directory, and the full numerical diagnostics, raw geographic scores, window table and traces accompany this report.

## Limitations

The new geographic scores use saved 100-state assignments, while the original primary audit uses the full retained CSV histories. Passing the original electoral screens does not resolve geographic mixing or the existing model and data limitations; these continuation outputs do not replace the registered freezes.
