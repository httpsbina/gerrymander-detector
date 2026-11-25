# Geographic continuation

I continue the six NC chains from 23,000 states and the eight Texas chains from 70,000 states in a separate campaign, while preserving `nc-baseline-23000`, `texas-baseline-70000` and their registered results. Each continuation retains its original seed, starting-map cohort, assignment, RNG state and step numbering, with the same sampler, population bounds, adjacency and 500-state warmup.

## Screens and schedule

I retain all fourteen previously measured geographic fields: silhouette, normalized population RMS radius, mean Polsby-Popper, mean distance, distance SD, pooled CV, inverse CV, mean district CV, internal boundary length, common-graph cut count, density-weighted boundary, area-normalized RMS radius, area-weighted Polsby-Popper and median Polsby-Popper. CV and inverse CV remain reciprocal measurements. Collapsed-centroid comparisons remain measurement sensitivity checks, rather than replacements for block-level distances.

Every geographic field must have rank-normalized split R-hat below 1.01 and bulk and tail ESS at least 400 within each starting cohort, 600 across all NC chains and 800 across all Texas chains. I also rerun the four original electoral/chain screens, mean/SD/quantile MCSE, half-history checks and the existing warmup sensitivity grid. Missing, failed or nonfinite diagnostics prevent a passing status.

I audit each state at every 5,000-state complete length, starting at 25,000 for NC and 75,000 for Texas. All existing observations remain in the histories. Geographic scores use every saved 100-state assignment, with the existing silhouette sample seed 20261109 and 2,048 locations; the raw chain CSVs remain unthinned. Eight single-threaded workers share the fourteen chains, with NC jobs entering each wave first, with checkpoints every 100 states and complete CSV segments every 1,000 states. A state pauses only after its cohorts and joint group pass the geographic and original primary screens, while the other state continues. There is no date or fixed simulation budget in the stopping rule.

## Runtime and records

I validate complete CSV coverage, checkpoint hashes, pinned packages, kernel fingerprints and replay before production. The existing platform-transition protocol preserves source checkpoints and records any runtime adapter separately. A complete valid replay difference can start a documented native segment; failed execution or an unexplained same-runtime mismatch stops continuation.

The campaign writes only under `outputs/analysis/geographic_continuation_20261118` in the source checkout. Source histories are linked read-only into a separate staging tree, and production uses separate output directories. Each completed wave has its own manifest and validation records; milestone audits have separate geographic and original-primary outputs. The controller holds an exclusive lock and stops on failed segment validation, preserving the attempt.

```sh
RESEARCH_PYTHON=../gerrymander-detector/.venv/science/bin/python
"$RESEARCH_PYTHON" -m paper.prepare_geographic_continuation \
  --source-root ../gerrymander-detector \
  --parallel-review paper/reviews/parallel-comparison-20261118 \
  --output-dir ../gerrymander-detector/outputs/analysis/geographic_continuation_20261118

PYTHONHASHSEED=0 "$RESEARCH_PYTHON" -m paper.geographic_continue \
  --source-root ../gerrymander-detector \
  --manifest ../gerrymander-detector/outputs/analysis/geographic_continuation_20261118/manifest.json \
  --measurement-cache outputs/analysis/geographic_measurement_20261109 \
  --output-dir ../gerrymander-detector/outputs/analysis/geographic_continuation_20261118/production
```

At audited milestones I archive the complete campaign boundary, source histories, measurement cache and registered inputs, then upload it to the existing draft backup release. Archive contents and the remote SHA-256 digest are checked. Backup failures are recorded separately from sampling progress, and the release remains draft.

## Limitations

Additional sampling can resolve slow geographic mixing but cannot remove the simulation-unit support mismatch or the documented Texas overlap warnings. Numerical screens do not certify uniform sampling, complete legal constraints or calibrated outlier probabilities. The earlier electoral freezes remain historical records; passing this continuation does not rewrite them or automatically establish full research readiness.
