# Texas and North Carolina initial campaign

I ran 26 chains across eight baseline and sensitivity conditions in November 2026, recording 122,000 states and retaining 109,000 after 500 warmup states per chain. All 44 primary metric/group combinations fell below the bulk-ESS screen. I keep this initial campaign separate from the continued baselines in the [project README](../../README.md).

I used Redistricting Data Hub inputs, with Dr. Eric Gerber advising the research at Northeastern. The [source report](../rdh-research-audit-2026-11-02/README.md) records the geographic construction and election checks.

## Runs and diagnostics

| Condition                        | Starting maps                        |   Chains × states | Population bound |
| -------------------------------- | ------------------------------------ | ----------------: | ---------------: |
| Texas baseline                   | Prior congressional map              |         4 × 4,000 |            ±0.1% |
| Texas population sensitivity     | Same prior map                       |         4 × 4,000 |            ±0.5% |
| NC block-union baseline          | 2023 and 2025                        | 3 × 5,000 per map |            ±0.5% |
| NC precinct-geometry sensitivity | 2023 and 2025                        | 3 × 5,000 per map |            ±0.5% |
| NC population sensitivity        | 2023 and 2025, block-union geography | 3 × 5,000 per map |              ±1% |

I used different seeds for the two NC starting-map groups within each condition, reusing labels across sensitivity conditions that I analyzed separately. The [workflow](../../docs/research_workflow.md) records when I added chains. I retained every recorded state without thinning and evaluated warmup at 0, 250, 500 and 1,000 states, using 500 for the primary analysis.

The sampler uses cut-edge choice and random-MST ReCom proposals, `node_repeats=2`, `max_attempts=1000`, pair reselection and always-accept for proposals satisfying the population and graph-contiguity constraints. I retain the parameters, seeds, commands and dataset fingerprints in the [campaign manifest](campaign_manifest.json) and [executed registries](executed_state_registries.json).

I screened each metric for rank-normalized split R-hat below 1.01 and bulk/tail ESS of at least 400 within the Texas and separate NC groups, or 600 for six-chain NC combinations. These are the recorded seat-count results:

| Condition                | Chains | Seat R-hat | Bulk ESS | Tail ESS | Mean MCSE (seats) |
| ------------------------ | -----: | ---------: | -------: | -------: | ----------------: |
| Texas baseline ±0.1%     |      4 |    1.03644 |    100.9 |    145.5 |            0.1198 |
| Texas sensitivity ±0.5%  |      4 |    1.12480 |     24.6 |    150.6 |            0.2518 |
| NC block-union / 2023    |      3 |    1.00924 |    210.3 |    553.4 |            0.0556 |
| NC block-union / 2025    |      3 |    1.01485 |    231.3 |    292.6 |            0.0547 |
| NC block-union / jointly |      6 |    1.01135 |    451.8 |    758.1 |            0.0385 |
| NC precinct / 2023       |      3 |    1.03460 |    119.9 |    239.5 |            0.0744 |
| NC precinct / 2025       |      3 |    1.01551 |    214.4 |    369.1 |            0.0578 |
| NC precinct / jointly    |      6 |    1.02705 |    319.9 |    573.0 |            0.0465 |
| NC ±1% / 2023            |      3 |    1.02876 |    223.7 |    313.3 |            0.0593 |
| NC ±1% / 2025            |      3 |    1.01194 |    165.0 |    315.9 |            0.0667 |
| NC ±1% / jointly         |      6 |    1.01897 |    365.2 |    599.9 |            0.0447 |

I measured Democratic-majority districts, efficiency gap, cut edges and Democratic median-minus-mean vote share. The [primary table](primary_diagnostics.csv) contains the 44 metric/group combinations; [diagnostics.csv](diagnostics.csv) contains all 176 metric/warmup views, with estimates and flags in [diagnostics.json](diagnostics.json). All 1,232 core estimates are finite.

For the Texas baseline, cut-edge R-hat is 1.13644, bulk ESS is 27.7 and mean MCSE is 17.45 edges; mean-median R-hat is 1.05979 with bulk ESS 47.3. Joint primary NC efficiency-gap R-hat is 1.02543 with bulk ESS 294.8.

![Texas traces](figures/tx_rebuild_trace.png)

NC joint seat bulk ESS is 487.7, 464.3, 451.8 and 401.4 across warmup settings 0, 250, 500 and 1,000, with R-hat 1.00876, 1.01200, 1.01135 and 1.01280. Texas baseline seat bulk ESS stays below 400 at each setting. I plotted all recorded states in the traces and used post-warmup average ranks for ties in the [22 trace/rank figures](figures/README.md). The [chain summaries](chain_summary.csv) retain autocorrelations and first/last-window changes, with all windows in [windows.csv](windows.csv).

![NC primary joint ranks](figures/nc_block_union_joint_rank.png)

## Enacted scores and tail observations

I score PLANC2333 at 8 Democratic-majority districts using the official block assignment and modeled presidential votes. In the initial Texas baseline, 4 of 14,000 retained states also have 8 districts, all in seed 3331 at steps 2,253, 2,256, 2,257 and 2,258. The full observed range is 8–17.

I replayed steps 2,200–2,258 from a stored checkpoint, matching all 59 CSV records. Each of the four target assignments has a distinct recomputed cut-edge fingerprint, and every one of the six pairwise unit-weighted partition distances is positive. Independent scoring gives 8 Democratic-majority districts for each, with the original population and graph-contiguity constraints satisfied. I keep the [assignments](tail_assignment_check/plan_assignments.csv), [verification and commands](tail_assignment_check/assignment_verification.json) and [replay configuration](tail_assignment_check/state.json); replay records are excluded from ensemble counts.

The Texas ±0.5% condition has zero states at or below 8 among its own 14,000 retained states. Its constant tail indicator returns nonfinite R-hat at every warmup setting, while ArviZ returns MCSE zero and ESS equal to the draw count.

NC's block-union baseline has 193 of 27,000 retained states at or below the enacted score of 3, comprising 58 from the 2023 group and 135 from the 2025 group. The precinct-geometry and ±1% conditions have 304 and 300, each among 27,000 retained states. I retain each condition separately in the [per-chain counts](enacted_tail_counts.csv) and [indicator diagnostics](enacted_tail_diagnostics.json).

## Population and geography comparisons

The wider population bounds give seat bulk ESS 24.6 for Texas ±0.5% and 365.2 for joint NC ±1%; both also fail R-hat. Sensitivity-minus-baseline mean seat differences are +0.13093 for Texas's population bound, +0.05563 / −0.05667 for NC precinct geometry from 2023 / 2025 starts, and −0.06667 / +0.04400 for NC's wider bound. NC's 2025-minus-2023 mean difference is −0.04022 on block unions and −0.15252 on precinct geometry.

I examined all 1,220 saved checkpoints, measuring the fraction of each county's population assigned to districts with a modeled Democratic presidential majority. I included zero-population units and kept post-warmup summaries separately. Among Texas counties above 500,000 population, the largest across-seed ranges in mean population fraction are:

| Texas county FIPS suffix | Population | Across-seed range in checkpoint mean population fraction |
| ------------------------ | ---------: | -------------------------------------------------------: |
| 491                      |    609,017 |                                                   0.3380 |
| 029                      |  2,009,324 |                                                   0.0992 |
| 453                      |  1,290,188 |                                                   0.0838 |
| 439                      |  2,110,640 |                                                   0.0745 |
| 201                      |  4,731,145 |                                                   0.0659 |

FIPS suffixes 491, 029, 453, 439 and 201 identify Williamson, Bexar, Travis, Tarrant and Harris. Williamson's range is 33.8 percentage points. Harris's last-ten minus first-ten checkpoint mean changes span +0.0091 to +0.1879 across chains, while Dallas changes in opposite directions across chains. I retain the [county summaries](county_chain_summary.csv), [across-chain ranges](county_chain_ranges.csv) and [checkpoint fingerprints](geography_audit.json).

## Comparing partitions

I used [variation of information](https://doi.org/10.1016/j.jmva.2006.11.013), measured in bits, to compare assignments independently of district labels. The global analysis covers 1,220 checkpoints and 159,990 pairs. I computed unit- and population-weighted distances separately within each condition; zero-population units contribute to the unit measure and have zero population weight.

For post-warmup pairs at least 2,000 states apart, with matched lag distributions across comparison categories, I obtain these mean population-weighted distances:

| Condition      | Within chain | Between chains, same starting map | Between starting maps |
| -------------- | -----------: | --------------------------------: | --------------------: |
| Texas baseline |      2.93988 |                           2.95174 |                   n/a |
| Texas ±0.5%    |      2.96859 |                           2.98761 |                   n/a |
| NC block-union |      2.62961 |                           2.63198 |               2.63028 |
| NC precinct    |      2.57550 |                           2.58450 |               2.58389 |
| NC ±1%         |      2.60352 |                           2.60076 |               2.59967 |

Within-chain and between-chain averages are close, including comparisons across NC starts. I find no clear global partition separation in these averages, although the county political-allocation summaries differ and the convergence diagnostics fail.

![Texas partition comparisons](partition_distances/tx_rebuild_distances.png)

I retain [lag summaries](partition_distances/distance_summary.csv), [reference-assignment distances](partition_distances/reference_distances.csv), [methods and fingerprints](partition_distances/partition_distances.json) and five condition heatmaps; pair-level tables stay with the local analysis outputs.

I also restricted the measure to counties with 2020 population at least 500,000, covering 12 Texas and three NC counties. The [coverage table](county_partition_distances/county_coverage.csv) records all 354 counties and selection status. I retained zero-population units in each selected county's unit-weighted comparison. Across 460 checkpoints, I computed 287,190 county-restricted pairs; selected post-warmup means at matched lags of at least 2,000 states are:

| County               | Within chain | Between chains, same starting map | Between starting maps |
| -------------------- | -----------: | --------------------------------: | --------------------: |
| Williamson, TX (491) |      1.68047 |                           1.68719 |                   n/a |
| Harris, TX (201)     |      2.91204 |                           2.87385 |                   n/a |
| Bexar, TX (029)      |      2.46998 |                           2.49500 |                   n/a |
| Guilford, NC         |      1.31593 |                           1.31436 |               1.31058 |
| Mecklenburg, NC      |      1.97258 |                           1.97215 |               1.96634 |
| Wake, NC             |      2.14245 |                           2.14563 |               2.14413 |

These internal-partition averages are also close within and between chains, including counties where political-allocation summaries differ.

![County-restricted Texas comparisons](county_partition_distances/tx_rebuild_county_distances.png)

The [contrasts](county_partition_distances/long_lag_contrasts.csv), [lag summaries](county_partition_distances/county_distance_summary.csv) and [fingerprints](county_partition_distances/county_partition_distances.json) retain every selected county's results.

## Input checks

I retained all 668,757 Texas blocks, population 29,145,505 and 9,712 simulation units, applying five `make_valid` ring repairs in a derived candidate. Eight overlaps remain, with the largest approximately 0.198461 m²; both graph constructions agree on adjacency.

NC retains all 236,638 blocks, population 10,439,388 and 2,681 common units, including Onslow. Block unions have zero overlaps and matching GerryChain/shared-boundary adjacency, while the precinct alternative differs by 47 edges. Both NC assignments score 3 Democratic-majority districts under presidential votes.

The [adopted-plan audit](adopted_plan_geometry.json) finds valid single polygons and zero positive-area overlaps for the 38 Texas districts and both sets of 14 NC districts. Both NC polygon population fields match the block master. I record election-source differences and enacted-plan election-model comparisons in the source report.

## Records and reproducing

The [portable manifest](campaign_manifest.json) uses repository-relative paths and preserves execution hashes. `manifest_sha256` identifies the original execution manifest and `publication_manifest_sha256` the portable copy; source, dataset, chain and checkpoint hashes retain their recorded values.

Both state-CLI audits match the full-audit results, the campaign planner reproduces all 26 definitions, and Texas and NC uninterrupted 120-state runs match split 100+20-state runs exactly. I recorded 62 passing tests without skips, plus dependency, formatting, syntax and whitespace checks in [verification.json](verification.json) and the original test output. Numerical checksums remain in [artifact_manifest.json](artifact_manifest.json); document checksums are in [documentation_checksums.json](../documentation_checksums.json).

I ran these commands from the repository root. They preserve the original output locations; I use new directories for repeated executions.

```sh
export MPLCONFIGDIR="$PWD/data/external/rdh/rebuild_2026-11-02/runtime/matplotlib312"
export TMPDIR="$PWD/.venv/test-runtime"
export UV_CACHE_DIR="$PWD/.venv/uv-cache"
.venv/science/bin/python src/chain/run_rebuild_campaign.py --output-dir outputs/analysis/rebuild_campaign_2026-11-02 --workers 4 --run
.venv/science/bin/python src/analysis/audit_rebuild_campaign.py --manifest outputs/analysis/rebuild_campaign_2026-11-02/manifest_with_constraint_sensitivity_v2.json --output-dir outputs/analysis/rebuild_campaign_2026-11-02/final_full_audit
.venv/science/bin/python src/analysis/plot_rebuild_campaign.py --manifest outputs/analysis/rebuild_campaign_2026-11-02/manifest_with_constraint_sensitivity_v2.json --output-dir outputs/analysis/rebuild_campaign_2026-11-02/final_full_figures
.venv/science/bin/python src/analysis/audit_checkpoint_geography.py --manifest outputs/analysis/rebuild_campaign_2026-11-02/manifest_with_constraint_sensitivity_v2.json --output-dir outputs/analysis/rebuild_campaign_2026-11-02/final_checkpoint_geography
.venv/science/bin/python src/analysis/audit_enacted_tail.py --manifest outputs/analysis/rebuild_campaign_2026-11-02/manifest_with_constraint_sensitivity_v2.json --audit-root outputs/analysis/rdh_rebuild_2026-11-02 --output-dir outputs/analysis/rebuild_campaign_2026-11-02/enacted_tail_audit
.venv/science/bin/python src/validation/audit_adopted_plan_geometry.py --source-root data/external/rdh/rebuild_2026-11-02 --audit-root outputs/analysis/rdh_rebuild_2026-11-02 --output-dir outputs/analysis/rdh_rebuild_2026-11-02/adopted_plan_geometry
.venv/science/bin/python main.py --nc --config configs/research_rebuild_2026-11-02.json --stage research-audit --campaign-manifest outputs/analysis/rebuild_campaign_2026-11-02/manifest_with_constraint_sensitivity_v2.json --report-dir outputs/analysis/rebuild_campaign_2026-11-02/state_cli_nc_full_audit
.venv/science/bin/python main.py --texas --config configs/research_rebuild_2026-11-02.json --stage research-audit --campaign-manifest outputs/analysis/rebuild_campaign_2026-11-02/manifest_with_constraint_sensitivity_v2.json --report-dir outputs/analysis/rebuild_campaign_2026-11-02/state_cli_tx_full_audit
.venv/science/bin/python src/chain/run_rebuild_campaign.py --output-dir outputs/analysis/rebuild_campaign_replay_check_2026-11-02
.venv/science/bin/python src/analysis/audit_partition_distances.py --manifest outputs/analysis/rebuild_campaign_2026-11-02/manifest_with_constraint_sensitivity_v2.json --checkpoint-audit outputs/analysis/rebuild_campaign_2026-11-02/final_checkpoint_geography/geography_audit.json --output-dir outputs/analysis/partition_distances_2026-11-02
.venv/science/bin/python src/analysis/audit_county_partition_distances.py --manifest outputs/analysis/rebuild_campaign_2026-11-02/manifest_with_constraint_sensitivity_v2.json --checkpoint-audit outputs/analysis/rebuild_campaign_2026-11-02/final_checkpoint_geography/geography_audit.json --global-analysis-dir outputs/analysis/partition_distances_2026-11-02 --output-dir outputs/analysis/county_partition_distances_2026-11-02
.venv/science/bin/python -m unittest discover -s tests -v
.venv/bin/uv pip check --python .venv/science/bin/python
```

## Limitations

The chains fail the convergence screens, so I do not treat their Monte Carlo errors as reliable accuracy guarantees. MCSE and window-stability acceptance criteria still need to be specified. The four Texas tail states occur within six steps of one chain; their frequency is descriptive. Zero observations and the constant indicator's zero MCSE leave probability and uncertainty unresolved, and none of these tail frequencies is a calibrated p-value.

Saved-checkpoint summaries leave sampler connectivity, causal constraint effects and distributional equivalence unresolved. Partition pairs share plans, so their count is not an effective sample size. Variation of information measures membership, while global averages can hide local differences; county-restricted distances also omit which outside units join a county and neither measure gives physical boundary displacement.

RDH block votes are modeled, with election-source differences, NC privacy noise, candidate effects and uniform-swing assumptions affecting interpretation. Population and election years differ. I scored alternative elections on enacted maps but have not run those models across the full ensemble.

Texas's eight overlaps remain unresolved; starting-map sensitivity belongs to the continued study. NC inherits RDH block-to-precinct membership assumptions. I checked district-polygon connectedness, while independent enacted block-graph equivalence remains outstanding. Population and graph-contiguity constraints cover only part of the legal and demographic requirements, and I have not established uniform sampling over valid maps. The historical chain files are unavailable, so the [earlier Texas report](../../docs/archive/texas-analysis-before-2026-11-rebuild.md) remains an unrevalidated record separate from this campaign and the continued baseline freezes.
