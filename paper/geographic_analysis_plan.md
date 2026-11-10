# Geographic comparison

I am extending the initial clustering pilot with three complementary measures: silhouette for separation between districts, normalized population RMS radius for within-district dispersion, and mean Polsby-Popper for boundary compactness. I will retain all three unless a calculation is unavailable or fails validation; their selection does not depend on whether the enacted maps look unusual. Radial CV stays in the exploratory record because a ring can have low CV without tight clustering.

I use every available 100-state checkpoint through the registered NC and Texas freezes, retaining the existing 500-state warmup for the main comparison. I report the checkpoint interval because these measurements cannot recover assignments that were not saved. I keep the original histories and freeze rules unchanged.

For radius, I use every Census block's population and projected polygon centroid, calculating district centers and sums of squared distances from weighted moments. This removes population sampling error for this block-centroid representation, though it does not locate residents within blocks.

For perimeter compactness, I build a separate measurement geography from the existing Census blocks, splitting simulation units wherever the enacted assignments split them. Every block, including zero-population blocks, remains in that geography. I aggregate both enacted and simulated assignments on those same pieces, without changing the simulation graph. Invalid geometries or positive-area overlaps stop the calculation; I apply no repairs. Shared-boundary arithmetic is checked against direct polygon unions.

For silhouette, I use the initial seed 20261109 and 2,048 population-proportional block draws on all saved checkpoints. I also repeat the original ten-checkpoint-per-chain comparison with independent seeds 20261110, 20261111 and 20261112, at 1,024 and 2,048 locations. I retain the first sample and report changes across samples, rather than selecting a preferred sample. Distances and areas use EPSG:5070; I compare pilot silhouette scores with ellipsoidal geodesic distances to assess projection sensitivity.

I report the enacted values and empirical ranks within each starting-map cohort and jointly, plus rank-normalized split R-hat, bulk and tail ESS, mean MCSE, warmup comparisons and half-history shifts for the new metrics. These checks describe the stored checkpoint series and do not change the original numerical freezes. Constant tail indicators have unavailable uncertainty estimates rather than zero error.

## Limitations

The ensemble already has population and boundary constraints, so its geographic distribution is conditional on those choices rather than uniform over all maps. A geographic outlier does not establish partisan intent or legal noncompliance. Block centroids, projected distances and geographic resolution remain modeling choices; the independent samples and distance comparison address parts of that uncertainty. Statewide averages can hide individual districts, so I also report enacted district scores and minimum district compactness.
