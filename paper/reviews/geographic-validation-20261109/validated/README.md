# Geographic comparison for discussion

I measured the enacted maps and every available frozen 100-state checkpoint without using votes or party labels. I retained the existing 500-state warmup, leaving 5,560 Texas and 1,350 NC checkpoint observations. These are saved states from correlated chains, rather than a count of independent maps.

| Map        | Measure                          | Enacted | Simulated median | Simulated 5th to 95th percentile | Sampled scores at or below enacted |
| ---------- | -------------------------------- | ------: | ---------------: | -------------------------------: | ---------------------------------: |
| Texas 2025 | Silhouette                       |  0.0248 |           0.1495 |                 0.1225 to 0.1756 |                           0 / 5560 |
| Texas 2025 | Normalized population RMS radius |  0.2755 |           0.1988 |                 0.1864 to 0.2285 |                        5560 / 5560 |
| Texas 2025 | Mean Polsby-Popper compactness   |  0.2220 |           0.1562 |                 0.1431 to 0.1700 |                        5560 / 5560 |
| NC 2023    | Silhouette                       |  0.1269 |           0.1949 |                 0.1575 to 0.2342 |                           4 / 1350 |
| NC 2023    | Normalized population RMS radius |  0.3327 |           0.2894 |                 0.2722 to 0.3124 |                        1346 / 1350 |
| NC 2023    | Mean Polsby-Popper compactness   |  0.2442 |           0.1893 |                 0.1653 to 0.2158 |                        1350 / 1350 |
| NC 2025    | Silhouette                       |  0.1220 |           0.1949 |                 0.1575 to 0.2342 |                           4 / 1350 |
| NC 2025    | Normalized population RMS radius |  0.3374 |           0.2894 |                 0.2722 to 0.3124 |                        1349 / 1350 |
| NC 2025    | Mean Polsby-Popper compactness   |  0.2495 |           0.1893 |                 0.1653 to 0.2158 |                        1350 / 1350 |

Texas and both NC maps have higher mean perimeter compactness than every retained checkpoint, while their silhouette scores are low and their population radii are high. These measurements describe different geographic properties, so I retain the contrast rather than combining them into one score.

## New-metric diagnostics

| State | Measure                          | Joint R-hat | Bulk ESS | Tail ESS |
| ----- | -------------------------------- | ----------: | -------: | -------: |
| NC    | Silhouette                       |      1.0031 |    680.6 |    962.1 |
| NC    | Normalized population RMS radius |      1.0053 |    589.7 |    837.7 |
| NC    | Mean Polsby-Popper compactness   |      1.0034 |   1144.5 |   1255.6 |
| TX    | Silhouette                       |      1.0084 |    756.8 |   2021.0 |
| TX    | Normalized population RMS radius |      1.0418 |    162.2 |    775.7 |
| TX    | Mean Polsby-Popper compactness   |      1.0022 |   2530.4 |   4796.3 |

Mean Polsby-Popper passes the original numerical reference screens within both starting-map cohorts and jointly in each state. Silhouette and radius fail one or more cohort or joint screens in both states, so the original electoral-metric freezes do not resolve geographic convergence. I have not extended or changed the frozen chains.

## What I measured

Silhouette compares average distance within a district with average distance to the nearest other district. Population RMS radius measures dispersion around each district’s population-weighted center, normalized by statewide population dispersion; I calculate it using every block’s population and centroid. Mean Polsby-Popper measures district area relative to squared perimeter, averaging the district scores. Higher silhouette and Polsby-Popper mean more separated or compact districts; higher radius means more dispersion.

I retain these three measures because they address separation, population dispersion and boundary shape. Radial CV remains in the earlier pilot, where its Texas rank changed with sample size and its interpretation was ambiguous.

## Checks

The common measurement partition contains 10,147 Texas pieces and 2,681 NC pieces, built from all 905,395 Census blocks, including zero-population blocks. It has no positive-area overlaps, and it preserves Texas enacted splits without changing any simulation unit or graph. I checked the perimeter arithmetic against direct polygon unions for each enacted map and every terminal chain assignment.

I repeated the silhouette pilot across four independent population-sample seeds, two sample sizes and projected versus ellipsoidal distances; sample_sensitivity.csv retains every comparison. diagnostics.csv reports R-hat, bulk and tail ESS and mean Monte Carlo error for every metric, separately by starting-map cohort and jointly. results.json also retains warmup and half-history comparisons.

## Limitations

The geographic results are conditional on the existing sampler, population tolerances and boundary constraints, so they describe this ensemble rather than a uniform distribution of possible maps. The original freeze does not certify convergence of these new measures; I report their diagnostics separately. Silhouette still approximates the statewide population using sampled block centroids, while the radius is population-exact only for the block-centroid representation. Repeated samples and geodesic distances assess parts of that approximation. Compactness uses a common Census-block boundary resolution, which may differ from official district polygon detail. Statewide averages can conceal individual districts, whose enacted and pilot scores are retained in district_scores.csv. An empirical zero count does not establish zero probability, and geometric unusualness does not establish partisan intent or legal noncompliance.

## Reproducing

```sh
nice -n 15 env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 python -m paper.geographic_geometry --source-root SOURCE_CHECKOUT --output-dir NEW_MEASUREMENT_CACHE
nice -n 15 env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 python -m paper.geographic_refinement --source-root SOURCE_CHECKOUT --measurement-cache NEW_MEASUREMENT_CACHE --output-dir NEW_REPORT_DIRECTORY
MPLCONFIGDIR=.venv/matplotlib python -m paper.geographic_validation_report NEW_REPORT_DIRECTORY --measurement-cache NEW_MEASUREMENT_CACHE
python -m unittest discover -s tests -v
```

Both output directories must be new. results.json records source and code hashes, package versions and every diagnostic; the cache inventory records all derived-file checksums.
