# State CLI

I run validation, geographic construction, simulation, continuation, and research audits through the state CLI, using the pinned Python 3.12 environment from the repository root.

## Status

```sh
export MPLCONFIGDIR="$PWD/data/external/rdh/rebuild_2026-11-02/runtime/matplotlib312"
export TMPDIR="$PWD/.venv/test-runtime"
export UV_CACHE_DIR="$PWD/.venv/uv-cache"
.venv/science/bin/python main.py --texas --config configs/research_rebuild_2026-11-02.json
.venv/science/bin/python main.py --nc --year 2023 --config configs/research_rebuild_2026-11-02.json
.venv/science/bin/python main.py --nc --year 2025 --config configs/research_rebuild_2026-11-02.json
```

I use the source-derived candidates in `configs/research_rebuild_2026-11-02.json`; `configs/states.json` retains earlier definitions. Status queries read the registry without starting a chain.

## Validate and build

```sh
.venv/science/bin/python main.py --nc --stage validate --source-root data/external/rdh/rebuild_2026-11-02 --report-dir outputs/analysis/new_nc_source_validation
.venv/science/bin/python main.py --texas --stage validate --source-root data/external/rdh/rebuild_2026-11-02 --report-dir outputs/analysis/new_tx_source_validation
.venv/science/bin/python main.py --nc --stage rebuild --source-root data/external/rdh/rebuild_2026-11-02 --block-master outputs/analysis/new_nc_source_validation/blocks/blocks_master.csv --report-dir outputs/analysis/new_nc_block_union_candidate --dry-run
```

I check block accounting and raw geometry separately. NC uses Census-block unions by default, while `--rebuild-geography precinct` selects the separate sensitivity candidate. The Texas builder applies the five recorded `make_valid` ring repairs. I select each constructed dataset explicitly in its registry.

## Simulate and continue

```sh
.venv/science/bin/python main.py --nc --year 2025 --config configs/research_rebuild_2026-11-02.json --stage simulate --steps 5000 --seed 2707 --dry-run
.venv/science/bin/python main.py --texas --config configs/research_rebuild_2026-11-02.json --stage simulate --steps 4000 --seed 1117 --resume-from outputs/analysis/rebuild_campaign_2026-11-02/tx_rebuild/checkpoints/tx_rebuild_20261102_checkpoint_eps0p001_seed1117_next4000.pkl --dry-run
```

I specify seeds, steps, configuration, and output paths explicitly. These examples use `--dry-run`; the second would append steps 4,000–7,999 from its version-2 checkpoint. The runner checks dataset and graph hashes, parameters, runtime, source, seed, assignment, and `PYTHONHASHSEED=0`, and stops on overlapping steps or checkpoint collisions.

I prepare the initial 26-chain campaign with:

```sh
.venv/science/bin/python src/chain/run_rebuild_campaign.py --output-dir outputs/analysis/new_campaign_plan
```

I add `--run --workers 4` to execute the prepared commands through `main.py`, keeping graph and population-bound experiments separate.

## Research audits

```sh
.venv/science/bin/python main.py --nc --config configs/research_rebuild_2026-11-02.json --stage research-audit --campaign-manifest outputs/analysis/rebuild_campaign_2026-11-02/manifest_with_constraint_sensitivity_v2.json --report-dir outputs/analysis/new_nc_research_audit
.venv/science/bin/python main.py --texas --config configs/research_rebuild_2026-11-02.json --stage research-audit --campaign-manifest outputs/analysis/rebuild_campaign_2026-11-02/manifest_with_constraint_sensitivity_v2.json --report-dir outputs/analysis/new_tx_research_audit
```

I audit every configured experiment for the selected state, checking segment continuity, seed and tolerance consistency, finite traces, checkpoint endpoints, and provenance. The four metrics are Democratic-majority districts, efficiency gap, cut edges, and mean-median. I record rank-normalized split R-hat, bulk/tail ESS, mean/SD/quantile MCSE, four warmup views, autocorrelation, and window summaries, with NC starting-map groups assessed separately and jointly.

## Verification

```sh
.venv/science/bin/python -m unittest discover -s tests -v
.venv/bin/uv pip check --python .venv/science/bin/python
```

I use new destination paths for repeated executions. The research environment pins the dependencies; the initial campaign's 100+20-state and uninterrupted 120-state runs matched complete CSV records.

## Limitations

Pennsylvania has no validated simulation inputs. The legacy `--stage audit` covers the earlier limited diagnostic set; I use `research-audit` for the complete configured study. Tests with fixtures check implementation behavior, while real-data checks establish the input and run record. I collect scientific limitations in the [campaign report](../deliverables/rebuild-campaign-2026-11-02/README.md#limitations).
