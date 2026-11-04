# State CLI

I use the state CLI to validate inputs, build geographic candidates and run simulations and audits. I run the commands below from the repository root in the pinned Python 3.12 environment, giving each repeated execution a new output directory.

## Inputs and construction

I select the rebuilt candidates through `configs/research_rebuild_2026-11-02.json`; `configs/states.json` retains the earlier definitions. A status query reads the registry without launching a chain.

```sh
export MPLCONFIGDIR="$PWD/data/external/rdh/rebuild_2026-11-02/runtime/matplotlib312"
export TMPDIR="$PWD/.venv/test-runtime"
export UV_CACHE_DIR="$PWD/.venv/uv-cache"
.venv/science/bin/python main.py --texas --config configs/research_rebuild_2026-11-02.json
.venv/science/bin/python main.py --nc --year 2023 --config configs/research_rebuild_2026-11-02.json
.venv/science/bin/python main.py --nc --year 2025 --config configs/research_rebuild_2026-11-02.json
```

I check block accounting separately from raw geometry, then select the constructed dataset explicitly in the registry. NC uses Census-block unions by default; `--rebuild-geography precinct` selects the sensitivity construction. The Texas builder applies the five documented `make_valid` ring repairs.

```sh
.venv/science/bin/python main.py --nc --stage validate --source-root data/external/rdh/rebuild_2026-11-02 --report-dir outputs/analysis/new_nc_source_validation
.venv/science/bin/python main.py --texas --stage validate --source-root data/external/rdh/rebuild_2026-11-02 --report-dir outputs/analysis/new_tx_source_validation
.venv/science/bin/python main.py --nc --stage rebuild --source-root data/external/rdh/rebuild_2026-11-02 --block-master outputs/analysis/new_nc_source_validation/blocks/blocks_master.csv --report-dir outputs/analysis/new_nc_block_union_candidate --dry-run
```

## Simulation and continuation

I specify the seed, steps, configuration and output paths for each run. These examples use `--dry-run`; the Texas continuation would append steps 4,000–7,999 from its version-2 checkpoint.

```sh
.venv/science/bin/python main.py --nc --year 2025 --config configs/research_rebuild_2026-11-02.json --stage simulate --steps 5000 --seed 2707 --dry-run
.venv/science/bin/python main.py --texas --config configs/research_rebuild_2026-11-02.json --stage simulate --steps 4000 --seed 1117 --resume-from outputs/analysis/rebuild_campaign_2026-11-02/tx_rebuild/checkpoints/tx_rebuild_20261102_checkpoint_eps0p001_seed1117_next4000.pkl --dry-run
```

The runner checks dataset and graph hashes, parameters, runtime, source, seed, assignment and `PYTHONHASHSEED=0`, stopping on overlapping steps or checkpoint collisions. I prepare the initial 26-chain campaign with:

```sh
.venv/science/bin/python src/chain/run_rebuild_campaign.py --output-dir outputs/analysis/new_campaign_plan
```

I add `--run --workers 4` to execute the commands through `main.py`, keeping graph and population-bound experiments separate.

## Audits and verification

I use `research-audit` for the full configured study, including segment continuity, seed and tolerance checks, finite traces, checkpoint endpoints and provenance. I record Democratic-majority districts, efficiency gap, cut edges and mean-median, with rank-normalized split R-hat, bulk/tail ESS, mean/SD/quantile MCSE, four warmup views, autocorrelation and window summaries. I assess NC starting-map groups separately and jointly.

```sh
.venv/science/bin/python main.py --nc --config configs/research_rebuild_2026-11-02.json --stage research-audit --campaign-manifest outputs/analysis/rebuild_campaign_2026-11-02/manifest_with_constraint_sensitivity_v2.json --report-dir outputs/analysis/new_nc_research_audit
.venv/science/bin/python main.py --texas --config configs/research_rebuild_2026-11-02.json --stage research-audit --campaign-manifest outputs/analysis/rebuild_campaign_2026-11-02/manifest_with_constraint_sensitivity_v2.json --report-dir outputs/analysis/new_tx_research_audit
```

```sh
.venv/science/bin/python -m unittest discover -s tests -v
.venv/bin/uv pip check --python .venv/science/bin/python
```

The initial campaign's uninterrupted 120-state runs matched split 100+20-state continuations in every CSV field. I retain that check with the pinned dependency record.

## Limitations

Pennsylvania has no validated simulation inputs. The legacy `--stage audit` computes a smaller diagnostic set. Fixture tests check implementation behavior; I use real-data checks to establish the input and run record, with scientific limitations in the [campaign report](../deliverables/rebuild-campaign-2026-11-02/README.md#limitations).
