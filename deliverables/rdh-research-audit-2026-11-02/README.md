# Texas and North Carolina: source audit and reconstruction

November 2, 2026. Gerrymander Detector, advised by Dr. Eric Gerber at Northeastern.

**Neither state is research-ready.** This package records new source-backed evidence, candidate geographies, election-model sensitivity, and validated continuation mechanics. It does not certify convergence or calibrated inference. Historical chain files and the proposed three-commit patch were unavailable in the permitted checkout; no historical chain was discarded, replaced, or treated as reproduced. New simulation results are a distinct campaign.

This analysis was conducted using data from the Redistricting Data Hub.

## Verified block-level evidence

Nine RDH archives were acquired under the approved noncommercial, nonpartisan terms. Their byte counts, checksums, source pages, and archive members are pinned in [the source manifest](../../configs/rdh_rebuild_sources_2026-11-02.json). Raw archives, block masters, GeoPackages, checkpoints, runtime files, and chain CSVs remain local and ignored by Git. No account credentials or signed download URLs are stored in this package.

| Measure                                    |      Texas | North Carolina |
| ------------------------------------------ | ---------: | -------------: |
| Unique 2020 Census blocks                  |    668,757 |        236,638 |
| Population                                 | 29,145,505 |     10,439,388 |
| Modeled 2024 Harris votes                  |  4,835,134 |      2,713,609 |
| Modeled 2024 Trump votes                   |  6,393,403 |      2,896,942 |
| Population blocks missing election records |          0 |              0 |
| Election blocks missing population records |          0 |              0 |
| Official plan assignments missing blocks   |          0 |              0 |
| Zero-population Census blocks retained     |    219,672 |         61,650 |

Population is Census P1 total population, not voting-age population. All block IDs were checked for state FIPS, length and uniqueness. The election, Census population and official plan files have exactly equal block sets. State totals reproduce the historical configuration; that agreement alone does not validate an election source against the canvass. Independent execution through `main.py --stage validate` reproduced the block-master CSVs byte for byte.

Texas PLANC2333 was scored using its official block equivalency: **8 Democratic-majority districts** under modeled presidential votes. The source includes **427 precincts split by PLANC2333**; no whole-precinct assignment was substituted for block scoring. Maximum relative district population deviation is approximately 0.00012695%.

Both NC plans score **3 Democratic-majority districts** under the same modeled presidential vote file. The 2023-to-2025 assignment change moves 18,826 blocks, population 543,381, and modeled votes 117,023 Democratic / 177,741 Republican. These are descriptive assignments and scores, not congressional election outcomes or calibrated probabilities.

## Election source limitations found, not corrected away

RDH's block allocations use modified 2020 voting-age population, precinct assignment procedures including nearest-precinct fallbacks, and integer rounding. They are modeled block votes, not observed block returns. Population and election years also differ. The zero-population audit retains 65 Texas blocks with modeled 2024 two-party votes despite zero 2020 population, totaling 543 Democratic and 450 Republican allocations. This alone does not establish an error or unlawful voting. NC has no such positive presidential allocations in its zero-population blocks.

Texas's block allocations reproduce the RDH precinct presidential counts exactly. However, the [November 25, 2024 Texas certificate](https://www.archives.gov/files/electoral-college/2024/ascertainment-texas.pdf) contains 116 more Harris votes and 194 more Trump votes. RDH's precinct metadata acknowledges small differences from the official canvass. No votes were scaled, imputed or redistributed to force agreement.

NC's block file contains one more modeled Trump vote than its precinct file, at `WAKE-:-16-09`. The [official NCSBE documentation](https://www.ncsbe.gov/results-data/election-results/historical-election-results-data) explains that precinct-sorted results include privacy noise and are not the official election totals. RDH documents a mixture of sorted and unsorted inputs.

The public unsorted [NCSBE return file](https://s3.amazonaws.com/dl.ncsbe.gov/ENRS/2024_11_05/results_pct_20241105.zip), downloaded and hashed separately, totals 2,715,375 Harris / 2,898,423 Trump. Its server modification date is December 3, 2024. RDH's block totals are lower by 1,766 / 1,481, with differences in 27 counties; summed absolute county differences are 1,794 / 1,495. Both positive and negative county discrepancies exist. These differences are measured, not all causally attributed to privacy noise.

The [November 26 NCSBE certification](https://s3.amazonaws.com/dl.ncsbe.gov/State_Board_Meeting_Docs/2024-11-26/Canvass/Certification%20of%20State%20Jurisdiction%20Contests%20112624.pdf) and [December 9 certificate](https://www.archives.gov/files/electoral-college/2024/ascertainment-north-carolina.pdf) instead give 2,715,378 / 2,898,424. That additional 3 / 1 discrepancy between official snapshots is retained explicitly. None of these snapshots is silently substituted for another or asserted to be the latest amended canvass.

Provider documentation also contains apparent template errors: the NC precinct README's first line says 2022 despite the 2024 fields and dataset, and the Texas PL dataset page's description mentions Ohio. Actual file identities were checked using state-coded block IDs, named candidate fields, population totals, and source URLs rather than titles alone.

## Geometry findings and approved candidates

### Texas

The raw 9,712-unit precinct and congressional layers each contain five ring self-intersections and eight positive-area overlap pairs. The largest overlap is approximately 0.198461 m².

The user approved a specific `make_valid` candidate repair for `121-4222`, `295-0106`, `401-0416`, `453-0152`, and `479-0252`. The repair script is restricted to the reviewed source archive checksum. All five repaired polygons remain polygons, are valid, and have zero measured Hausdorff displacement; the maximum absolute area change is approximately 7.16×10⁻⁷ m². Original files were untouched.

The candidate retains every unit, block, population and vote. Its graph has 26,860 edges and one component; all 38 prior-map districts are contiguous. GerryChain and positive shared-boundary adjacency agree on every edge. The starting population deviation is 0.0524163%, within the unchanged ±0.1% constraint. **Eight source overlap pairs remain documented**, so the repairs are not a blanket geography certification.

### North Carolina

The all-races source layer has 2,658 valid polygons and no positive-area overlaps. Its congressional-split layer has 2,678 valid polygons but 44 tiny overlap pairs, the largest approximately 3.13×10⁻⁸ m².

The reconstructed precinct-based common candidate has 2,681 units. It preserves all block totals and both plans' district totals and contiguity. It has 57 positive-area overlap pairs. The unreassigned Onslow coverage residual is approximately 0.001211 m². No snapping, sliver reassignment or geometry repair was performed on this candidate.

GerryChain produces 7,584 edges on that candidate; exact positive shared-boundary adjacency produces 7,581. Three sampler-only contacts are recorded with measurements. Rounding experiments at 10⁻⁸, 10⁻⁶, 10⁻⁴ and 0.01 US survey feet produce different graphs, ranging from 7,592 to 7,598 edges. No rounding precision was selected as a production rule.

A separately constructed alternative unions all **236,638 valid Census block geometries** by the audited precinct / 2023 / 2025 membership. It has:

- The same 2,681 unit IDs, assignments, block counts, populations and modeled votes.
- No invalid or empty units, no positive-area overlaps, no isolates and one connected graph.
- Contiguous districts under both plans.
- Exactly matching GerryChain and shared-boundary graphs, with 7,581 edges.

The two candidate graphs differ by **47 edges**: 25 precinct-only and 22 block-union-only. Equal edge counts therefore do not establish equal topology. The sum of unitwise symmetric-difference areas is 774,347 m², with a largest unit difference of 155,680 m². This sum can count transferred territory twice; it is not a statewide coverage-loss estimate. Precinct membership still inherits RDH's block-assignment assumptions.

The user approved the block-union candidate as the **new NC baseline**, retaining the precinct candidate as a separate topology sensitivity experiment. Old and new chains must not be pooled as one experiment.

![Onslow split](figures_source/nc_onslow_block_union.png)

The Onslow SW19 unit contains 208 blocks and population 7,450. The 2025 district-1 piece has 131 blocks, population 4,853, and modeled votes 805 Democratic / 2,116 Republican. The district-3 piece has 77 blocks, population 2,597, and modeled votes 434 / 1,146. Both pieces were assigned to district 3 in 2023.

## Election-model sensitivity on enacted plans

![Election choice](figures_source/election_model_sensitivity.png)

Texas PLANC2333 scores 8 Democratic-majority districts with either presidential or Senate votes. Under the Senate model, the smallest two-party margin is only 224 modeled votes; a +1 percentage-point Democratic uniform swing produces 10 districts, versus 8 under the presidential model. These scores therefore should not be generalized to all election models.

NC's 2023 / 2025 plans score 3 / 3 using presidential votes, 4 / 3 using attorney-general votes, and 12 / 13 using gubernatorial votes. Candidate strength differs substantially across these elections. An additional uniform-swing scenario normalizes every election to the presidential statewide two-party share; all three normalized models then score 3 / 3. This is an assumed comparison model, not a correction to the observed returns and not a claim of model independence.

![Normalized election sensitivity](figures_source/nc_election_normalization_sensitivity.png)

These are enacted-plan sensitivities. **Alternative-election scoring over every ensemble state has not been performed.** No descriptive frequency is presented as a calibrated p-value, and no zero count is interpreted as zero probability.

## Continuation bug found and fixed

The initial 100+20 versus 120-state continuation test failed. Saving Python's RNG state and the assignment was insufficient: unordered cut-edge and subgraph iteration could change proposals after reconstruction. A second check produced identical plans but tiny differences in floating diagnostic reductions.

The new implementation orders cut-edge iteration, node/edge ordering for IID spanning-tree weight draws, and district ordering for diagnostic reductions. It retains the intended uniform cut-edge-choice and random-MST mechanisms, population constraints, `node_repeats=2`, and pair-reselection settings. This is a new recorded implementation lineage, not a claim of legacy bitwise equivalence or a uniform ensemble over valid plans.

The final synthetic-grid test and real Texas/NC checks produce **identical complete CSV records** for uninterrupted 120-state and split 100+20-state runs. Earlier failed probes and logs remain preserved and are excluded from all research ensembles.

Version-2 checkpoints verify dataset and graph fingerprints, requested parameters, software/runtime versions, source-code hashes, seed, assignment fingerprint and `PYTHONHASHSEED`. Legacy version-1 checkpoints are refused because their provenance cannot establish these properties. Existing checkpoints and overlapping CSV segments are refused before simulation; writes use exclusive creation. The periodic/final checkpoint boundary is tested without overwriting the same checkpoint twice.

## Runtime and verification

The original system environment was recorded and left intact. GerryChain 0.3.2 failed importing on Python 3.9.6, despite metadata allowing installation. An isolated Python **3.12.16** environment was therefore created at `.venv/science`; use `.venv/science/bin/python`, not the retained outer Python-3.9 trial. Exact package versions are in [the research environment freeze](../../requirements-research-macos-arm64-py312.txt). Imports, ArviZ reference diagnostics and dependency consistency checks pass.

The full suite passed **48 tests** before publication, including malformed/duplicate block rejection, zero-population preservation, disconnected districts, point-only contacts, tiny overlap adjacency, nonfinite diagnostics, protected paths, checkpoint endpoint/provenance mismatches and exact continuation. Later changes receive their own verification record. Final fixtures are confined to `.venv/test-runtime`, outside research data/results paths; earlier labeled temporary test fixtures were cleaned after their tests.

Both raw-source `main.py --stage validate` commands returned **exit 1**, because unresolved geometry findings require review. Their block-level subaudits passed and produced identical masters to the independent runs. Successful acquisition, completed audits, passing software tests and research readiness are separate statuses.

No Python formatter or linter was configured in the checkout. Python syntax and whitespace checks are run; no formatter/linter pass is claimed. Prettier 3.9.10 is installed only in the ignored local tooling environment to check changed Markdown and JSON. No existing research outputs are reformatted or overwritten.

## Commands used

Commands run from the repository root. Existing destinations now refuse collisions; choose new output paths when repeating a full audit or candidate build.

```sh
export MPLCONFIGDIR="$PWD/data/external/rdh/rebuild_2026-11-02/runtime/matplotlib312"
export TMPDIR="$PWD/.venv/test-runtime"
export UV_CACHE_DIR="$PWD/.venv/uv-cache"
MPLCONFIGDIR="$MPLCONFIGDIR" TMPDIR="$TMPDIR" .venv/science/bin/python -m unittest discover -s tests -v
.venv/bin/uv pip check --python .venv/science/bin/python
python3 src/validation/audit_rdh_sources.py --state north_carolina --source-root data/external/rdh/rebuild_2026-11-02 --output-dir outputs/analysis/rdh_rebuild_2026-11-02/nc_block_audit
python3 src/validation/audit_rdh_sources.py --state texas --source-root data/external/rdh/rebuild_2026-11-02 --output-dir outputs/analysis/rdh_rebuild_2026-11-02/tx_block_audit
.venv/science/bin/python main.py --nc --stage validate --source-root data/external/rdh/rebuild_2026-11-02 --report-dir outputs/analysis/rdh_cli_validation_2026-11-02/nc
.venv/science/bin/python main.py --texas --stage validate --source-root data/external/rdh/rebuild_2026-11-02 --report-dir outputs/analysis/rdh_cli_validation_2026-11-02/tx
.venv/science/bin/python src/data_prep/rebuild_nc_common.py --source-root data/external/rdh/rebuild_2026-11-02 --block-master outputs/analysis/rdh_rebuild_2026-11-02/nc_block_audit/blocks_master.csv --output-dir outputs/analysis/rdh_rebuild_2026-11-02/nc_common_candidate
.venv/science/bin/python src/data_prep/rebuild_texas_candidate.py --source-root data/external/rdh/rebuild_2026-11-02 --block-master outputs/analysis/rdh_rebuild_2026-11-02/tx_block_audit/blocks_master.csv --output-dir outputs/analysis/rdh_rebuild_2026-11-02/tx_candidate
.venv/science/bin/python src/data_prep/rebuild_nc_block_union.py --source-root data/external/rdh/rebuild_2026-11-02 --block-master outputs/analysis/rdh_rebuild_2026-11-02/nc_block_audit/blocks_master.csv --output-dir outputs/analysis/rdh_rebuild_2026-11-02/nc_block_union_candidate
.venv/science/bin/python src/validation/audit_adjacency_sensitivity.py --dataset outputs/analysis/rdh_rebuild_2026-11-02/nc_block_union_candidate/nc_block_union_candidate.gpkg --output outputs/analysis/rdh_rebuild_2026-11-02/nc_block_union_adjacency.json
.venv/science/bin/python src/analysis/audit_nc_precision_sensitivity.py --dataset outputs/analysis/rdh_rebuild_2026-11-02/nc_common_candidate/nc_common_candidate.gpkg --output outputs/analysis/rdh_rebuild_2026-11-02/nc_precision_sensitivity.json
.venv/science/bin/python src/validation/audit_nc_official_returns.py --official-zip data/external/ncsbe/rebuild_2026-11-02/results_pct_20241105.zip --block-master outputs/analysis/rdh_rebuild_2026-11-02/nc_block_audit/blocks_master.csv --output outputs/analysis/rdh_rebuild_2026-11-02/nc_official_county_comparison.json
.venv/science/bin/python src/analysis/plot_source_audit.py --audit-root outputs/analysis/rdh_rebuild_2026-11-02 --output-dir deliverables/rdh-research-audit-2026-11-02/figures_source
.venv/science/bin/python main.py --nc --config configs/research_rebuild_2026-11-02.json
.venv/science/bin/python main.py --texas --config configs/research_rebuild_2026-11-02.json
```

The same continuation command was run for each state, using its dataset, tolerance and seed, with fresh `_v3` paths after the earlier failures:

```sh
.venv/science/bin/python src/validation/check_continuation.py --dataset outputs/analysis/rdh_rebuild_2026-11-02/nc_block_union_candidate/nc_block_union_candidate.gpkg --assignment-col CONG_DIST --epsilon 0.005 --seed 707 --output-dir outputs/analysis/rdh_rebuild_2026-11-02/nc_continuation_probe_v3
.venv/science/bin/python src/validation/check_continuation.py --dataset outputs/analysis/rdh_rebuild_2026-11-02/tx_candidate/tx_candidate.gpkg --assignment-col CONG_DIST --epsilon 0.001 --seed 1117 --output-dir outputs/analysis/rdh_rebuild_2026-11-02/tx_continuation_probe_v3
```

Source acquisition used approved, short-lived RDH download links with a browser-compatible user agent and RDH referrer, supplied through stdin to the local acquisition helper. The initial unheadered request returned HTTP 403. Signed query strings were not saved; public source pages, unsigned file paths, checksums and acquisition times are retained instead.

## Research steps still required

The running campaign must be evaluated using all recorded chains, starting maps and predefined sensitivity conditions. Rank-normalized split R-hat, bulk/tail ESS, MCSE, autocorrelation, trace/rank plots, window behavior and warmup sensitivity are required; NC starting-map groups are assessed separately and jointly within each geometry. No different-geography or different-tolerance chains are pooled. Numerical screening follows [Vehtari et al.](https://arxiv.org/abs/1903.08008), with a strict R-hat limit of 1.01 and ESS floor `max(400, 100 × chains)`; MCSE and stability criteria still need scientific review.

The implemented sampler chooses cut edges, generates random-MST proposals and applies population/contiguity constraints with pair reselection. It does not establish uniform sampling or full legal compliance; [ReCom's methodological scope](https://arxiv.org/abs/1911.05725) is distinct from a legally exhaustive ensemble. Texas starting-map sensitivity, ensemble-wide alternative-election scoring, election-source/noise uncertainty, any failed diagnostic, and persistent chain disagreement remain research work. Neither successful execution nor the volume of generated maps establishes readiness.
