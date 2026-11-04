# Texas shared-length audits

I retain every baseline state beyond 45,000. The four baseline chains completed 46,000 states each, ending at step 45,999 with continuation checkpoints at 46,000; I hold those complete histories while the dispersed cohort catches up.

When all dispersed chains reach 45,000, I compare the first 45,000 states from every chain with the existing 500-state warmup. This shared-prefix audit leaves the additional baseline states in their original CSVs and checkpoints. I then resume each baseline from 46,000 and each dispersed chain from 45,000, auditing both cohorts and all eight chains at the next shared length of 50,000 and every 5,000 states thereafter.

## Reproducing

I launch the controller from validated complete manifests and a new destination:

```sh
PYTHONHASHSEED=0 MPLCONFIGDIR="$PWD/.venv/matplotlib" caffeinate -i \
  .venv/science/bin/python src/chain/run_texas_shared_prefix.py \
  --baseline-manifest BASELINE_MANIFEST \
  --dispersed-manifest DISPERSED_MANIFEST \
  --output-dir NEW_CONTINUATION_DIRECTORY
```

This schedule replaces the earlier passing-baseline catch-up schedule in `docs/texas_cohort_schedule.md`. I keep the earlier record and the tagged NC files unchanged. The receiving-machine scripts use this controller after replay validation.

## Limitations

The 45,000-state comparison uses shared prefixes while retaining longer histories, so I exclude it from freeze decisions and continue to the next shared length that includes every existing observation. The cohort and joint thresholds, sampler, constraints, target distribution and warmup remain unchanged. NC stays frozen at `nc-baseline-23000`.
