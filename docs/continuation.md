# Baseline continuation and transfer

Results freeze under [the primary convergence rule](freeze_rule.md), never because a date or a simulation budget has been reached. North Carolina is frozen at 23,000 states per chain under `nc-baseline-23000`. Texas retains all four original chains and all four independent dispersed-start chains.

## Local runs

The Texas controller uses up to eight single-threaded sampling processes. It saves checkpoints every 100 states and commits complete CSV segments at most 1,000 states apart. It audits every primary metric at each cohort's 5,000-state milestones. The first complete, equal-length joint milestone is 50,000 states per chain; if it fails, all eight chains continue in 5,000-state increments until both cohorts and the joint analysis pass.

```sh
PYTHONHASHSEED=0 MPLCONFIGDIR="$PWD/.venv/matplotlib" caffeinate -i \
  .venv/science/bin/python src/chain/run_texas_until_freeze.py \
  --baseline-manifest outputs/analysis/convergence_campaign_2026-11-02/tx_seat_continuation/manifest_005.json \
  --dispersed-manifest outputs/analysis/convergence_campaign_2026-11-02/texas_dispersed_launch/manifest.json \
  --output-dir outputs/analysis/convergence_campaign_2026-11-02/tx_primary_continuation \
  --first-joint-milestone 50000
```

That command is already running. Do not launch a second controller against its output directories. Each `manifest_*.json` records a completed CSV boundary. A checkpoint beyond that boundary may belong to an unfinished segment and must not be used to skip observations.

## Transfer

`continuation-snapshot-2026-11-02` is a draft backup release. Keep it in draft status; never publish it.

Export complete boundaries with the existing pinned requirements:

```sh
MPLCONFIGDIR="$PWD/.venv/matplotlib" .venv/science/bin/python \
  -m src.chain.export_continuation \
  --manifest NC_MANIFEST BASELINE_MANIFEST DISPERSED_MANIFEST \
  --output-dir NEW_TRANSFER_DIRECTORY
```

The export copies datasets, complete CSV histories, matching final and preceding checkpoints, source files, configurations, frozen results, and checksums. It excludes credentials and the local virtual environment. Different cohort lengths are allowed in the transfer; joint convergence is evaluated only at a later common complete milestone.

On the receiving machine, use a fresh checkout of `research/baseline-convergence`, unpack the archive there, and run:

```sh
RESEARCH_PYTHON=/path/to/matching/python3.12 ./resume.sh
```

For offline setup on a compatible ARM Mac, unpack the separate `science-environment-macos-arm64-py312.tar.gz` asset into the same directory, then use `./resume_offline.sh`. This preserves the working standalone Python build and all pinned scientific packages without downloading replacements. Environment file checksums and source-side replay receipts accompany the [draft transfer release](https://github.com/httpsbina/gerrymander-detector/releases/tag/untagged-785d91d5e891559ad717).

The accompanying `research-history.bundle` can create the checkout without network access: `git clone -b research/baseline-convergence research-history.bundle NEW_PROJECT_DIRECTORY`. It preserves the branch and NC freeze tag without copying credentials or Git configuration. Freeze commits and tags require an existing Bina author and committer identity; the scripts never configure or replace it.

The script creates a virtual environment if needed, installs the pinned packages, verifies file checksums, and replays the last 100 recorded states of every chain into separate validation directories. A matching runtime requires every CSV field, final assignment, plan hash, provenance record, and random state to match. Replayed states are validation outputs and are never added to the ensemble. North Carolina remains frozen; Texas resumes both cohorts.

Use `./resume.sh --verify-only` to run only the transfer checks. A successful replay on the source laptop is a source-side check, not certification of an untested receiving machine.

### Native-platform segments

On another ARM Mac or Linux machine, keep the same Python release and pinned package versions. A different build or operating system first requires identical dataset, graph, population/vote, configuration, sampler, and checkpoint-code fingerprints. The current assignment must still satisfy the original population and contiguity constraints. The original checkpoints remain untouched; separately hashed adapter checkpoints preserve their assignments, RNG states, seeds, and next-step indices with the receiving runtime's provenance.

The native runtime then attempts the same 100-state replay. If it matches, the receipt records an exact cross-platform replay. If it completes with valid finite outputs but differs from the source trajectory, production resumes from the original transfer-boundary state as a new documented segment. The receipt marks the last source step, first native step, both runtime profiles, and the end of bit-for-bit reproducibility. The probe's alternative trajectory is excluded. Step numbering and the existing warmup continue without a reset, and the observations remain one chain rather than additional independent chains.

This exception does not waive missing dependencies, changed sampling inputs, changed Python releases, failed execution, incomplete probes, or a replay failure in the same recorded runtime. Those cases stop for investigation. `--exact-only` retains the stricter matching-runtime policy. Transition receipts and their source files are checked before later simulation blocks and audits, and included in subsequent exports. Linux execution is certified only after these checks run on the actual receiving machine.

## Frozen outputs

```sh
MPLCONFIGDIR="$PWD/.venv/matplotlib" .venv/science/bin/python reproduce_paper.py \
  --output-dir NEW_REPRODUCTION_DIRECTORY
```

`configs/paper_freezes.json` registers frozen states. `results.json` contains their numerical results. Reproduction verifies input checksums, regenerates diagnostic figures and numerical tables, and requires exact equality with the stored numbers. Additional paper figures or tables must be registered in this pipeline before citation.

The primary freeze is a numerical stopping decision. Data provenance, modeled election allocations, geographic uncertainties, and the implemented ReCom distribution remain documented limitations; convergence alone does not establish legal compliance or uniform sampling.
