# Baseline freeze rule

Recorded November 2, 2026, before evaluating further continuation results.

A state freezes only when all four primary metrics pass simultaneously:
Democratic seat count, efficiency gap, cut edges, and Democratic median-minus-mean district vote share.
Each metric must have rank-normalized split R-hat strictly below 1.01 and both bulk and tail effective sample sizes at least `max(400, 100 × chains)`.
Every diagnostic must execute and be finite. Missing or failed checks prevent freezing.

Apply these screens jointly and within every starting-map group. North Carolina has two three-chain groups (2023 and 2025, ESS at least 400 each), and a six-chain joint analysis (ESS at least 600). Texas retains its four original baseline chains and adds four dispersed-start chains: assess the original and dispersed cohorts separately (ESS at least 400 each) and all eight jointly (ESS at least 800). Each dispersed map has one chain, so an individual-map R-hat cannot be estimated; the four dispersed maps constitute the dispersed initialization cohort. Do not label single-chain diagnostics as a passing starting-map group.

Use the existing 500-state warmup and retain every subsequent state, with no additional thinning. Joint analyses require equal complete chain lengths, compatible sampling kernels, and validated checkpoint lineage. Do not truncate longer chains to manufacture a passing comparison. Preserve every earlier segment, seed, and starting map.

Continue North Carolina beyond 18,000 states per chain until all joint and group primary screens pass simultaneously. Evaluate Texas at every 5,000 states per chain, including every primary metric. Continue both states without a calendar-based freeze or a fixed total simulation budget. November 16 is a transfer deadline, not a scientific stopping rule. Do not change the sampler, constraints, thresholds, or target distribution.

Before freezing, also run the existing Monte Carlo error, trace, window stability, warmup sensitivity, and starting-map checks. Record their complete outputs and unresolved scientific limitations. A primary numerical freeze is distinct from a claim that the model or data meet every research-readiness requirement. No unavailable or nonfinite diagnostic may be presented as passing.

For each frozen state, preserve immutable chain segments, matching checkpoints, datasets, configuration, software versions, exact commands, source fingerprints, and file checksums. Create a state-specific Git tag identifying the freeze manifest. Register only verified frozen outputs in `reproduce_paper.py`, and record every numeric table and figure source in `results.json`. Reproduction must fail on a checksum mismatch or an unfrozen input. Do not write paper prose.
