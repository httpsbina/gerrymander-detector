# State-configured research CLI

The state CLI covers validation, geographic construction, simulation, continuation and diagnostics. See the [source audit](../deliverables/rdh-research-audit-2026-11-02/README.md) and [campaign results](../deliverables/rebuild-campaign-2026-11-02/README.md).

Run from the repository root with the verified Python 3.12 environment:

```sh
export MPLCONFIGDIR="$PWD/data/external/rdh/rebuild_2026-11-02/runtime/matplotlib312"
export TMPDIR="$PWD/.venv/test-runtime"
export UV_CACHE_DIR="$PWD/.venv/uv-cache"
.venv/science/bin/python main.py --texas --config configs/research_rebuild_2026-11-02.json
.venv/science/bin/python main.py --nc --year 2023 --config configs/research_rebuild_2026-11-02.json
.venv/science/bin/python main.py --nc --year 2025 --config configs/research_rebuild_2026-11-02.json
```

Status is read-only. The original `configs/states.json` remains available for historical definitions; the new registry explicitly selects the source-derived candidates. `--penn` remains secondary and has no validated simulation inputs.

## Validate and build candidates

RDH acquisition requires authorized access. Checksums, source pages, metadata and limitations are recorded in `configs/rdh_rebuild_sources_2026-11-02.json`. Existing output directories are refused; use new paths for another execution.

```sh
.venv/science/bin/python main.py --nc --stage validate --source-root data/external/rdh/rebuild_2026-11-02 --report-dir outputs/analysis/new_nc_source_validation
.venv/science/bin/python main.py --texas --stage validate --source-root data/external/rdh/rebuild_2026-11-02 --report-dir outputs/analysis/new_tx_source_validation
.venv/science/bin/python main.py --nc --stage rebuild --source-root data/external/rdh/rebuild_2026-11-02 --block-master outputs/analysis/new_nc_source_validation/blocks/blocks_master.csv --report-dir outputs/analysis/new_nc_block_union_candidate --dry-run
```

Validation runs both block accounting and raw-source geometry checks. It returns a failure status when geometry requires review, even if block accounting passes. It does not repair source data. NC rebuild defaults to the Census-block-union baseline. Explicit `--rebuild-geography precinct` creates the separate precinct sensitivity candidate. Texas rebuild applies only the five make_valid ring repairs to the checksum-restricted source; eight source overlaps remain documented. Select a constructed dataset explicitly in the state registry.

## Simulate and continue

Simulation requires explicit `--seed` and `--steps`. Always inspect the configuration and output namespace. These commands are dry runs; they start no chains:

```sh
.venv/science/bin/python main.py --nc --year 2025 --config configs/research_rebuild_2026-11-02.json --stage simulate --steps 5000 --seed 2707 --dry-run
.venv/science/bin/python main.py --texas --config configs/research_rebuild_2026-11-02.json --stage simulate --steps 4000 --seed 1117 --resume-from outputs/analysis/rebuild_campaign_2026-11-02/tx_rebuild/checkpoints/tx_rebuild_20261102_checkpoint_eps0p001_seed1117_next4000.pkl --dry-run
```

The second command would append steps 4,000–7,999 under the recorded version-2 checkpoint lineage. The runner verifies dataset/graph fingerprints, parameters, runtime, source-code hashes, seed, assignment and `PYTHONHASHSEED`. It refuses unverifiable legacy checkpoints, overlapping CSV steps and checkpoint collisions. The CLI supplies `PYTHONHASHSEED=0` when unset. Texas and NC 100+20 versus 120-state continuation checks matched complete CSV records exactly.

The campaign launcher prepares all 26 separately labeled baseline and sensitivity commands. Without `--run`, it only writes a new manifest and per-experiment registries:

```sh
.venv/science/bin/python src/chain/run_rebuild_campaign.py --output-dir outputs/analysis/new_campaign_plan
```

Adding `--run --workers 4` executes every prepared command through `main.py`. The exact completed campaign manifest and historical registrations are preserved in the campaign deliverable. Reused seeds across sensitivity conditions do not establish independent comparisons. No graph or tolerance conditions are pooled.

## Full diagnostics through the state CLI

```sh
.venv/science/bin/python main.py --nc --config configs/research_rebuild_2026-11-02.json --stage research-audit --campaign-manifest outputs/analysis/rebuild_campaign_2026-11-02/manifest_with_constraint_sensitivity_v2.json --report-dir outputs/analysis/new_nc_research_audit
.venv/science/bin/python main.py --texas --config configs/research_rebuild_2026-11-02.json --stage research-audit --campaign-manifest outputs/analysis/rebuild_campaign_2026-11-02/manifest_with_constraint_sensitivity_v2.json --report-dir outputs/analysis/new_tx_research_audit
```

`research-audit` includes **every experiment for the selected state** in the manifest. It verifies segment continuity, seed/tolerance consistency, finite traces, final checkpoint endpoints and provenance, and refuses unconfigured segments. It runs rank-normalized split R-hat, bulk/tail ESS, mean/SD/quantile MCSE, four warmup views, autocorrelation and window summaries for seats, efficiency gap, cut edges and mean–median. NC initialization groups are assessed separately and jointly within each compatible condition. Trace/rank plotting and geographic checkpoint diagnostics have separate recorded commands in the campaign report.

The legacy `--stage audit` remains a limited historical auditor. Both audit stages refuse an existing destination; `--report-dir` can select a new one. A completed audit returns its execution status and reports convergence flags separately in the result files.

## Verification and scope

```sh
.venv/science/bin/python -m unittest discover -s tests -v
.venv/bin/uv pip check --python .venv/science/bin/python
```

The complete scientific suite requires the pinned research environment; fixture tests alone establish no real-data validity. No Python formatter/linter is configured. Changed Markdown/JSON use Prettier; Python uses syntax and whitespace checks.

Scientific interpretation and outstanding research checks are collected in the campaign report’s [Limitations](../deliverables/rebuild-campaign-2026-11-02/README.md#limitations).
