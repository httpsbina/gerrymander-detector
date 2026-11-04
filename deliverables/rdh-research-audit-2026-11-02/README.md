# Texas and North Carolina source rebuild

I rebuilt the inputs from nine Redistricting Data Hub archives in November 2026, with Dr. Eric Gerber advising the research at Northeastern. I checked the block records before constructing the geographic candidates, then compared the enacted assignments under different election models. The [campaign report](../rebuild-campaign-2026-11-02/README.md) covers the simulations that followed.

## Block records and assignments

| Measure                                    |      Texas | North Carolina |
| ------------------------------------------ | ---------: | -------------: |
| Unique 2020 Census blocks                  |    668,757 |        236,638 |
| Census P1 total population                 | 29,145,505 |     10,439,388 |
| Modeled 2024 Harris votes                  |  4,835,134 |      2,713,609 |
| Modeled 2024 Trump votes                   |  6,393,403 |      2,896,942 |
| Population blocks missing election records |          0 |              0 |
| Election blocks missing population records |          0 |              0 |
| Official plan assignments missing blocks   |          0 |              0 |
| Zero-population blocks retained            |    219,672 |         61,650 |

I checked each block ID's state FIPS, length and uniqueness; within each state, the Census, election and official assignment files contain identical block sets. Running the validation independently through the state CLI reproduced the block-master CSVs byte for byte.

I score Texas PLANC2333 at block resolution because its official assignment splits 427 precincts. It produces 8 Democratic-majority districts under the modeled presidential votes, with maximum population deviation approximately 0.00012695%. Both NC maps produce 3 Democratic-majority districts under the same vote allocation; between the 2023 and 2025 assignments, 18,826 blocks change districts, containing population 543,381 and modeled votes 117,023 Democratic / 177,741 Republican.

## Election inputs

RDH allocates precinct votes to blocks using modified voting-age population, precinct membership procedures and integer rounding. I retain 65 zero-population Texas blocks with positive modeled presidential votes, totaling 543 Democratic and 450 Republican votes. NC has no such allocations among its zero-population blocks.

The Texas block totals match the RDH precinct counts exactly. Compared with those values, the [November 25, 2024 certificate](https://www.archives.gov/files/electoral-college/2024/ascertainment-texas.pdf) contains 116 more Harris and 194 more Trump votes; RDH's metadata records small differences from the official canvass.

In NC, the block allocation has one more Trump vote than the precinct file at `WAKE-:-16-09`. RDH describes mixed precinct-sorted and unsorted inputs, and [NCSBE documents privacy noise in sorted files](https://www.ncsbe.gov/results-data/election-results/historical-election-results-data).

| NC source snapshot                                 |    Harris |     Trump |
| -------------------------------------------------- | --------: | --------: |
| RDH modeled block allocation                       | 2,713,609 | 2,896,942 |
| NCSBE unsorted file, modified December 3, 2024     | 2,715,375 | 2,898,423 |
| November 26 certification / December 9 certificate | 2,715,378 | 2,898,424 |

I compared the [December 3 unsorted snapshot](https://s3.amazonaws.com/dl.ncsbe.gov/ENRS/2024_11_05/results_pct_20241105.zip) with RDH and found differences in 27 counties. Net differences are 1,766 Harris and 1,481 Trump votes; summed absolute county differences are 1,794 and 1,495, with both signs represented. The [November 26 certification](https://s3.amazonaws.com/dl.ncsbe.gov/State_Board_Meeting_Docs/2024-11-26/Canvass/Certification%20of%20State%20Jurisdiction%20Contests%20112624.pdf) and [December 9 certificate](https://www.archives.gov/files/electoral-college/2024/ascertainment-north-carolina.pdf) add another 3 Harris and 1 Trump votes relative to that unsorted snapshot. I kept the RDH values without redistributing the differences.

## Geographic construction

The Texas source precinct and congressional layers each have 9,712 units, five ring self-intersections and eight positive-area overlap pairs, with the largest overlap approximately 0.198461 m². I applied `shapely.make_valid` in a derived candidate to `121-4222`, `295-0106`, `401-0416`, `453-0152` and `479-0252`, preserving the source archive and its checksum. Each repaired unit is a valid Polygon with zero measured Hausdorff displacement; the largest absolute area change is approximately 7.16 × 10⁻⁷ m².

The Texas candidate retains every unit, block, population and vote. GerryChain and positive shared-boundary adjacency agree on 26,860 edges; the graph is connected and all 38 prior-map districts are contiguous. The starting population deviation is 0.0524163%.

NC's all-races precinct layer has 2,658 valid polygons and zero positive-area overlaps. The congressional-split layer has 2,678 valid polygons and 44 overlap pairs, with a largest area of approximately 3.13 × 10⁻⁸ m². Combining the two assignments on the precinct-based geography gives 2,681 units and exact block totals, with 57 overlap pairs and an Onslow residual of approximately 0.001211 m². I obtain 7,584 GerryChain edges and 7,581 positive shared-boundary edges; coordinate-rounding scenarios give 7,592–7,598 edges. I retained the original coordinates in that candidate.

For the baseline, I instead unioned all 236,638 Census blocks by precinct / 2023 / 2025 membership. This preserves the same 2,681 IDs, block counts, populations, modeled votes and assignments. Every unit is valid and nonempty, both plans are contiguous, and overlaps and isolates are zero. GerryChain and shared-boundary adjacency agree on 7,581 edges.

The graphs differ by 47 edges: 25 occur only in the precinct graph and 22 only in the block-union graph. The summed unitwise symmetric-difference area is 774,347 m², with a largest unit difference of 155,680 m². I use block unions for the baseline and precinct geometry for a separate sensitivity experiment.

![Onslow split](figures_source/nc_onslow_block_union.png)

Onslow SW19 contains 208 blocks and population 7,450. Its 2025 district-1 piece contains 131 blocks, population 4,853 and modeled votes 805 Democratic / 2,116 Republican; the district-3 piece contains 77 blocks, population 2,597 and votes 434 / 1,146. Both pieces were assigned to district 3 in 2023.

## Election-model comparison

![Election models](figures_source/election_model_sensitivity.png)

PLANC2333 produces 8 Democratic-majority districts under both presidential and Senate votes. The Senate model's smallest two-party margin is 224 modeled votes; adding a uniform Democratic swing of 1 percentage point gives 10 districts in the Senate model and 8 in the presidential model.

NC's 2023 / 2025 assignments produce 3 / 3 Democratic-majority districts under presidential votes, 4 / 3 under attorney-general votes and 12 / 13 under gubernatorial votes. After a uniform swing normalizes each election to the presidential statewide two-party share, all three models produce 3 / 3.

![Statewide-share normalization](figures_source/nc_election_normalization_sensitivity.png)

## Records and reproducing

This analysis uses Redistricting Data Hub data. I keep source pages, archive members, byte counts and SHA-256 hashes in the [source manifest](../../configs/rdh_rebuild_sources_2026-11-02.json), with measurements in [evidence.json](evidence.json) and current document checksums in [documentation_checksums.json](../documentation_checksums.json).

I used Python 3.12.16 and the [pinned packages](../../requirements-research-macos-arm64-py312.txt). Version-2 checkpoints retain dataset and graph fingerprints, source hashes, parameters, versions, seed, assignment and RNG state. Stable cut-edge, spanning-tree input and district iteration order let the reconstructed Texas, NC and synthetic-grid continuations match every CSV record between uninterrupted 120-state runs and split 100+20-state runs.

I ran the commands below from the repository root. They record the original output locations; I use new directories when repeating the work. The [state CLI guide](../../docs/state_cli.md) describes the stages.

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

```sh
.venv/science/bin/python src/validation/check_continuation.py --dataset outputs/analysis/rdh_rebuild_2026-11-02/nc_block_union_candidate/nc_block_union_candidate.gpkg --assignment-col CONG_DIST --epsilon 0.005 --seed 707 --output-dir outputs/analysis/rdh_rebuild_2026-11-02/nc_continuation_probe_v3
.venv/science/bin/python src/validation/check_continuation.py --dataset outputs/analysis/rdh_rebuild_2026-11-02/tx_candidate/tx_candidate.gpkg --assignment-col CONG_DIST --epsilon 0.001 --seed 1117 --output-dir outputs/analysis/rdh_rebuild_2026-11-02/tx_continuation_probe_v3
```

## Limitations

Population is measured in 2020 and elections in 2024. I use modeled block votes, retaining election-source differences and NC privacy noise. Texas's eight overlaps remain in the candidate; NC geography depends on the block-membership construction. Summed unitwise symmetric differences count some transferred territory more than once. Legacy checkpoints lack the provenance fields needed for verified continuation. I describe the sampling and inference limits in the [campaign report](../rebuild-campaign-2026-11-02/README.md#limitations).
