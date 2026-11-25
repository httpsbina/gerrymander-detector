# Parallel geographic and electoral comparison

I compare geographic structure and electoral outcomes on the same saved maps. The geographic scores use Census population and block locations without votes, while the electoral scores regroup the existing modeled block allocations of 2024 election returns under each assignment. I keep these as separate measurements, then examine their descriptive association within the reference ensemble.

## Mean distance and variation

For each block b, I use its 2020 Census population p_b, centroid x_b and assigned district D. The district center is the population-weighted mean of its block centroids, and r_b is the Euclidean distance from x_b to that center. The statewide population-weighted mean radial distance and its population standard deviation are:

\[
\mu_r=\frac{\sum_b p_b r_b}{\sum_b p_b},\qquad
\sigma_r=\sqrt{\frac{\sum_b p_b(r_b-\mu_r)^2}{\sum_b p_b}}.
\]

I calculate CV = sigma_r / mu_r and inverse CV = mu_r / sigma_r. I use standard deviation rather than variance because both ratios are then dimensionless. I also retain each district's CV and its population-weighted mean across districts; that average is a different quantity from the statewide pooled CV. Inverse CV is a reciprocal transformation of the same per-map information, rather than an additional independent measure. Averaging inverse scores is not the same as taking the inverse of an average score.

These ratios describe relative variation in distances. They do not measure whether distances are short: a ring can have identical distances from its center even when its radius is large. I therefore retain the mean, standard deviation and RMS distance alongside the ratios. I check RMS squared = mean squared + SD squared for every assignment and compare its normalized RMS with the earlier all-block moment calculation.

## Matched maps and election data

I pair records by state, starting-map group, seed, recorded step and plan hash. A checkpoint at next step N contains recorded state N-1. The primary comparison uses every available 100-state checkpoint after the unchanged 500-state warmup. The full-history electoral summaries remain separate, since the chain CSVs contain more observations than the saved assignments.

I extend the local election scoring to the complete frozen Texas and NC checkpoint sets, preserving all earlier scores. Texas PLANC2333 is scored from its block assignments; both NC plans use the validated common geography. I use every statewide Democratic-versus-Republican contest already selected in the local election model, with no new election data, statewide normalization or uniform swing. An independent bincount implementation checks the tally for every saved plan and election.

I compare mean distance, CV, silhouette, population radius and perimeter compactness with the seat score using descriptive Spearman coefficients, separately by chain and starting-map cohort and jointly. I do not calculate IID p-values from correlated chain observations. Election-specific plots show the modeled statewide two-party share, the ensemble's observed range and median, and enacted scores; the points are separate elections, rather than a fitted swing curve.

## Diagnostics and output

I retain rank-normalized split R-hat, bulk and tail ESS, mean MCSE, half-history comparisons and the existing warmup sensitivity grid. The additional prewarmup election scores are used only for sensitivity checks. I record each unavailable or nonfinite value, retain every election and chain, and compare numerical screens with the existing minima without changing the freezes.

The technical and general summaries draw their numbers from the same registered output files. The output also records whether each enacted geographic value lies inside the observed reference range, so I do not extrapolate a geography-adjusted electoral comparison beyond that support.

## Limitations

The reference ensemble retains its existing sampling constraints and simulation units; Texas enacted boundaries can split units that the sampled plans cannot split. The original Texas sampler geography retains its documented overlap warnings, while the separate block-derived measurement geography is non-overlapping. Population locations are block-centroid proxies using 2020 counts, and block votes are modeled allocations of 2024 returns. These are not actual 2026 congressional results. Some geographic diagnostics remain unresolved, so finite MCSE values do not establish adequate precision. Small correlation coefficients do not establish independence or causation. Counts and ranks describe observed states, not calibrated probabilities of gerrymandering. The original frozen results remain unchanged.

## Reproducing

The module commands and file checksums are recorded in paper/reviews/parallel-comparison-20261118. The analysis uses the preserved pinned environment and existing source files; no dependencies or data are added.
