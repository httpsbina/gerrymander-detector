# Texas cohort scheduling

I continue the four baseline chains to the first 5,000-state audit milestone where all four primary metrics pass their cohort screens. I then hold that complete history while the four dispersed chains catch up to the same length, keeping every recorded state.

At that length, I audit both cohorts and all eight chains jointly. If any screen fails, I extend every chain by 5,000 states and repeat the equal-length audits. The cohort ESS threshold remains 400 and the joint threshold remains 800, with R-hat below 1.01 and the same 500-state warmup. NC remains frozen at `nc-baseline-23000`.

## Reproducing

I run the updated scheduler from validated complete manifests, using a new destination:

```sh
PYTHONHASHSEED=0 MPLCONFIGDIR="$PWD/.venv/matplotlib" caffeinate -i \
  .venv/science/bin/python src/chain/run_texas_matched.py \
  --baseline-manifest BASELINE_MANIFEST \
  --dispersed-manifest DISPERSED_MANIFEST \
  --output-dir NEW_CONTINUATION_DIRECTORY
```

This scheduling rule replaces the earlier fixed first-joint milestone in `docs/continuation.md`. I retain that document and the tagged NC record unchanged. Receiving-machine replay checks now launch the matched scheduler after validation.

## Limitations

A passing cohort audit only pauses that cohort; freezing still requires both cohorts and the joint analysis to pass at the same complete length, followed by the recorded finite diagnostic and reproduction checks. The sampler, target distribution and constraints are unchanged.
