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

Export complete boundaries with the existing pinned requirements:

```sh
MPLCONFIGDIR="$PWD/.venv/matplotlib" .venv/science/bin/python \
  -m src.chain.export_continuation \
  --manifest NC_MANIFEST BASELINE_MANIFEST DISPERSED_MANIFEST \
  --output-dir NEW_TRANSFER_DIRECTORY
```

The export copies datasets, complete CSV histories, matching final and preceding checkpoints, source files, configurations, frozen results, and checksums. It excludes credentials and the local virtual environment. Different cohort lengths are allowed in the transfer; joint convergence is evaluated only at a later common complete milestone.

On the receiving machine, unpack the archive and run:

```sh
RESEARCH_PYTHON=/path/to/matching/python3.12 ./resume.sh
```

The script creates a virtual environment if needed, installs the pinned packages, verifies file checksums and the recorded runtime, and replays the last 100 recorded states of every chain into separate validation directories. Every CSV field, final assignment, plan hash, provenance record, and random state must match before sampling resumes. Replayed states are validation outputs and are never added to the ensemble. North Carolina remains frozen; Texas resumes both cohorts.

Use `./resume.sh --verify-only` to run only the transfer checks. A successful replay on the source laptop is a source-side check, not certification of an untested receiving machine. The current checkpoints require the recorded macOS ARM64 Python build and package profile; Linux or a different Python build is rejected. The target-machine replay must pass before claiming exact continuation there.

## Frozen outputs

```sh
MPLCONFIGDIR="$PWD/.venv/matplotlib" .venv/science/bin/python reproduce_paper.py \
  --output-dir NEW_REPRODUCTION_DIRECTORY
```

`configs/paper_freezes.json` registers frozen states. `results.json` contains their numerical results. Reproduction verifies input checksums, regenerates diagnostic figures and numerical tables, and requires exact equality with the stored numbers. Additional paper figures or tables must be registered in this pipeline before citation.

The primary freeze is a numerical stopping decision. Data provenance, modeled election allocations, geographic uncertainties, and the implemented ReCom distribution remain documented limitations; convergence alone does not establish legal compliance or uniform sampling.
