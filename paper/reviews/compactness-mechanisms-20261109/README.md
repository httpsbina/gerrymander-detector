# Why the geographic measures differ

I scored the same frozen assignments with alternative boundary and area weightings, while keeping the original chains and numerical freezes unchanged. The comparison uses all retained saved checkpoints after the existing 500-state warmup.

| Map        | Measure                       |   Enacted | Simulated median | Sampled values at or below enacted |
| ---------- | ----------------------------- | --------: | ---------------: | ---------------------------------: |
| NC 2023    | Internal boundary, km         |   3,618.3 |          4,266.5 |                           0 / 1350 |
| NC 2025    | Internal boundary, km         |   3,504.9 |          4,266.5 |                           0 / 1350 |
| NC 2023    | Common-graph cut adjacencies  |       779 |              731 |                        1185 / 1350 |
| NC 2025    | Common-graph cut adjacencies  |       761 |              731 |                        1039 / 1350 |
| NC 2023    | Density-weighted boundary     |  33,075.2 |         40,218.6 |                           2 / 1350 |
| NC 2025    | Density-weighted boundary     |  33,243.4 |         40,218.6 |                           2 / 1350 |
| NC 2023    | Uniform-area radius           |    0.3189 |           0.2992 |                        1257 / 1350 |
| NC 2025    | Uniform-area radius           |    0.3154 |           0.2992 |                        1220 / 1350 |
| NC 2023    | Area-weighted Polsby-Popper   |    0.2446 |           0.2119 |                        1224 / 1350 |
| NC 2025    | Area-weighted Polsby-Popper   |    0.2647 |           0.2119 |                        1335 / 1350 |
| NC 2023    | Median district Polsby-Popper |    0.2701 |           0.1790 |                        1350 / 1350 |
| NC 2025    | Median district Polsby-Popper |    0.2719 |           0.1790 |                        1350 / 1350 |
| Texas 2025 | Internal boundary, km         |  12,576.7 |         15,251.3 |                           0 / 5560 |
| Texas 2025 | Common-graph cut adjacencies  |     3,401 |            2,747 |                        5560 / 5560 |
| Texas 2025 | Density-weighted boundary     | 113,291.1 |        125,498.6 |                           9 / 5560 |
| Texas 2025 | Uniform-area radius           |    0.3603 |           0.3530 |                        3420 / 5560 |
| Texas 2025 | Area-weighted Polsby-Popper   |    0.2609 |           0.1642 |                        5560 / 5560 |
| Texas 2025 | Median district Polsby-Popper |    0.2074 |           0.1424 |                        5560 / 5560 |

Internal boundary length is shorter for all three enacted maps than for every retained checkpoint, even though cut-adjacency counts are higher than their simulated medians. Counting crossings and measuring their physical length therefore give different assessments of the same boundaries.

Density-weighted boundary length also remains below the simulated median for every enacted map, so this weighting does not reverse the perimeter result. Texas uniform-area radius is much less unusual than its population radius. The median district Polsby-Popper score remains above every retained checkpoint for all three maps; the perimeter advantage is not confined to the arithmetic mean.

## County contributions

I decomposed squared normalized population radius into additive county contributions, then compared each enacted contribution with its ensemble mean. The largest positive contributions are:

Texas 2025: El Paso 0.007129; Travis 0.005773; Denton 0.004723; Bexar 0.003954; Ector 0.002232.

NC 2023: Cumberland 0.006679; Guilford 0.005340; Robeson 0.003405; Caldwell 0.002805; Forsyth 0.002533.

NC 2025: Cumberland 0.006679; Guilford 0.005340; Robeson 0.003405; Caldwell 0.002805; Forsyth 0.002533.

Texas seed 2227 has the largest positive half-history change in squared population radius. Its mean radius moves from 0.196000 to 0.206872; El Paso, Webb, Taylor, Bell, Bexar contribute the largest increases. County half-history differences add exactly to the change in mean squared radius, rather than the change in mean radius.

## Methods and checks

The boundary comparison uses the common Census-block measurement graph, with physical length and adjacent-pair population density fixed across all plans. Stored sampler cut-edge counts are retained only for simulated plans; enacted comparisons use the common measurement graph because Texas assignments split simulation units. Uniform-area radius integrates the polygon interiors, preserving components and subtracting holes. County moments use every block’s 2020 Census population and centroid.

I checked polygon areas and centroids against the geometry engine, the fixed-state-boundary perimeter identity for every assignment, and the county sum identity for every assignment. results.json includes rank-normalized split R-hat, bulk and tail ESS, mean MCSE and half-history checks for every new measure and starting-map cohort. warmup_sensitivity.json retains the existing 0, 250, 500 and 1,000 warmup comparisons.

The measurement choices are described in [geographic_measures.md](../../../docs/geographic_measures.md), with the primary references [Tapp](https://arxiv.org/html/2501.02325) and [Barnes and Solomon](https://arxiv.org/html/1803.02857).

## Numerical reference screens

| State | Cohort              | Measure                      |  R-hat | Bulk ESS | Tail ESS | Reference ESS |
| ----- | ------------------- | ---------------------------- | -----: | -------: | -------: | ------------: |
| NC    | nc_block_union_2023 | Density-weighted boundary    | 1.0115 |    522.7 |    505.0 |           400 |
| NC    | nc_block_union_2025 | Common-graph cut adjacencies | 0.9990 |    371.3 |    584.3 |           400 |
| NC    | nc_block_union_2025 | Uniform-area radius          | 1.0154 |    567.1 |    663.8 |           400 |
| TX    | joint               | Uniform-area radius          | 1.0158 |    535.3 |   1587.7 |           800 |
| TX    | tx_dispersed        | Uniform-area radius          | 1.0194 |    285.6 |   1106.8 |           400 |

The table lists every new metric and cohort combination that misses the original numerical reference screens; diagnostics.csv retains the complete set. These screens are comparisons for the new measurements, with the original freezes unchanged.

## Limitations

These are descriptive comparisons within the implemented ensemble; they do not identify intent or establish legal compliance. The original geographic radius and silhouette have unresolved convergence, which also limits interpretation of their county attribution. Alternative weightings are sensitivity measurements, not new acceptance rules or changes to the sampler. Uniform-area measurements include source water areas, and population radius still represents residents by block centroids. County contributions can offset one another and are not causal effects. All ranks and counts describe the saved checkpoint series, rather than calibrated probabilities.

## Reproducing

```sh
nice -n 15 env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 MPLCONFIGDIR=.venv/matplotlib python -m paper.compactness_mechanisms --source-root SOURCE_CHECKOUT --measurement-cache MEASUREMENT_CACHE --geographic-review paper/reviews/geographic-validation-20261109/validated --output-dir NEW_REPORT_DIRECTORY
MPLCONFIGDIR=.venv/matplotlib python -m paper.check_compactness_mechanisms --source-root SOURCE_CHECKOUT --review-dir NEW_REPORT_DIRECTORY
MPLCONFIGDIR=.venv/matplotlib python -m paper.compactness_partition_check --review-dir NEW_REPORT_DIRECTORY --measurement-cache MEASUREMENT_CACHE
MPLCONFIGDIR=.venv/matplotlib python -m paper.compactness_mechanism_report NEW_REPORT_DIRECTORY --measurement-cache MEASUREMENT_CACHE
MPLCONFIGDIR=.venv/matplotlib python -m paper.check_compactness_mechanisms --source-root SOURCE_CHECKOUT --review-dir NEW_REPORT_DIRECTORY --measurement-cache MEASUREMENT_CACHE --county-distances-only
python -m unittest discover -s tests -v
```

NEW_REPORT_DIRECTORY must be new. The measurement cache is produced by paper/geographic_geometry.py, and all underlying inputs are existing research files. The result records source hashes and package versions.
