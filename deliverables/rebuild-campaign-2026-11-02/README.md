# Texas and North Carolina: completed new-source campaign

Research advised by Dr. Eric Gerber, Northeastern University. **Execution completed; neither state is research-ready.** All 26 new-source chains completed their full configured lengths. All numerical diagnostics ran, but all 44 primary metric/group combinations fail their bulk-ESS screen. These are current measurements from the actual files, not the historical Texas 30,000-state run or NC six-chain summary.

The companion [source and methodological audit](../rdh-research-audit-2026-11-02/README.md) documents the acquired sources, exact block coverage, approved geometry changes, Onslow split, election-source discrepancies and exact continuation checks. This analysis was conducted using data from the Redistricting Data Hub.

## What was run and preserved

- Texas: four independent-seed baseline chains × 4,000 states at ±0.1% population tolerance; four separately labeled sensitivity chains × 4,000 states at ±0.5%.
- NC block-union baseline: three chains from the 2023 map and three from the 2025 map, each 5,000 states at ±0.5%.
- NC precinct-geography sensitivity: the same two three-chain starting-map groups and full lengths, separately labeled at ±0.5%.
- NC population sensitivity: both three-chain starting-map groups on the block-union geography, each 5,000 states at ±1%.

Total: **122,000 recorded states**, including initial states and warmup; **109,000 states** remain under the configured 500-state warmup view. These counts are not independent sample sizes. Nothing was thinned, truncated, discarded or replaced to improve diagnostics. Earlier failed probes and technical launch logs remain preserved outside research ensembles. Historical datasets/chains/checkpoints and the named three-commit patch were unavailable; no historical continuation or patch application is claimed.

The original launcher started 15 chains. A fourth Texas seed was added before diagnostic inspection; ten population-sensitivity chains were registered after the first NC low-ESS results, to investigate constraints. This timing is recorded rather than described retrospectively as a wholly preregistered campaign. Distinct seeds are used across NC starting maps within each condition. Reused seed labels across different graph/tolerance conditions are not assumed independent and do not justify pooling or paired standard errors.

## Current convergence results

Configured primary warmup is 500 states per chain. These seat diagnostics are part of the full four-metric audit:

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

Screens use R-hat strictly below 1.01 and bulk/tail ESS at least `max(400, 100 × chains)`: 400 for the four-chain Texas or three-chain NC groups, 600 for each six-chain NC combination. These conservative numerical screens are not complete research-readiness criteria. No existing limit was loosened and no sensitivity condition replaces a baseline.

Full evidence: [44 primary metric results](primary_diagnostics.csv), [176 metric/warmup diagnostic sets](diagnostics.csv), [complete diagnostics with flags, warnings and provenance](diagnostics.json), [per-chain means and autocorrelations](chain_summary.csv), and [every configured window](windows.csv). All 176 sets returned finite rank-normalized split R-hat, bulk/tail ESS, MCSE of mean/SD, and MCSE of 5th/95th quantiles: **1,232 finite numerical estimates**. Finite values do not imply adequate mixing. Discrete quantile MCSE can be zero when estimated quantiles coincide; that does not establish zero overall uncertainty. MCSE estimates under failed convergence are not reliable accuracy guarantees.

The other metrics also fail. Texas baseline cut-edge R-hat is **1.13644**, bulk ESS **27.7**, and mean MCSE **17.45 edges**; mean–median R-hat is **1.05979**, bulk ESS **47.3**. The combined primary NC efficiency-gap R-hat is **1.02543**, bulk ESS **294.8**. Seat diagnostics alone would miss important behavior.

![Texas full-state traces](figures/tx_rebuild_trace.png)

All groups have warmup views at 0, 250, 500 and 1,000 states. The primary NC joint seat bulk ESS is respectively **487.7, 464.3, 451.8 and 401.4**, always below 600. Its corresponding R-hat values are **1.00876, 1.01200, 1.01135 and 1.01280**. Choosing a different warmup does not establish convergence. Texas primary seat bulk ESS also remains below 400 in every warmup view.

There are **22 complete trace/rank figures**, covering every experiment separately and all three compatible NC joint groups. See the [figure index](figures/README.md). Traces show every recorded state. Rank plots preserve ties with average ranks; the empty bins of discrete seat ranks are not themselves a convergence failure.

![NC primary joint ranks](figures/nc_block_union_joint_rank.png)

## Investigation of persistent disagreement

### Enacted-score tail counts change the Texas descriptive claim

The current Texas baseline contains **4 of 14,000 retained states with 8 modeled Democratic-majority districts**, all from seed 3331 at steps 2,253, 2,256, 2,257 and 2,258. They have four distinct plan hashes but are tightly clustered in time. Therefore PLANC2333's block-scored result of 8 is **not below every observed baseline state in this new campaign**. The descriptive fraction is approximately 0.0286%; it is not a calibrated p-value or an established ensemble probability. The unavailable historical run is not retroactively changed or reproduced.

Texas's wider-tolerance sensitivity has **zero such retained states out of 14,000**. Its constant tail indicator produces a **nonfinite R-hat** at every checked warmup. ArviZ reports MCSE zero and ESS equal to draw count for that constant indicator; these are not evidence of zero uncertainty, independent samples, or zero probability. The core four-metric diagnostics remain finite as reported above; this additional tail diagnostic is nonfinite and independently prevents readiness. The baseline rare indicator's favorable R-hat also cannot overcome four events in one short cluster and failed full-chain diagnostics.

For NC, the primary graph has **193 of 27,000** retained states scoring at or below 3 modeled Democratic-majority districts: 58 from 2023 starts and 135 from 2025 starts. The precinct and wider-tolerance conditions have 304 and 300 such states respectively, each out of its own 27,000 retained states. These are separate descriptive counts under unconverged conditions. See [every chain's counts](enacted_tail_counts.csv) and [all rare-indicator diagnostics and warmup views](enacted_tail_diagnostics.json). None is converted into a calibrated significance claim.

### Constraint and geographic evidence

A higher population tolerance did not solve mixing: Texas seat ESS is 24.6 under ±0.5%, and NC combined seat ESS is 365.2 under ±1%. Both sensitivities have failed R-hat screens. These finite campaigns cannot isolate a causal tolerance effect from Monte Carlo error, initial-map dependence and differences in the sampled support.

The descriptive sensitivity-minus-baseline mean seat differences are +0.13093 for Texas population tolerance; +0.05563 / −0.05667 for NC precinct geography from 2023 / 2025 starts; and −0.06667 / +0.04400 for NC ±1% population tolerance. No confidence interval, calibrated test or equivalence conclusion is attached to these differences. Similar means do not prove identical distributions or a negligible graph effect.

NC 2025-minus-2023 mean seat differences are −0.04022 on the primary graph and −0.15252 on the precinct graph. The starting-map groups are individually unconverged, so neither value establishes removal of initialization effects.

The geographic audit uses **every one of the 1,220 saved checkpoints**, including warmup, to locate chain differences. It measures each county's population fraction assigned to districts with a modeled Democratic presidential majority. It does not estimate congressional outcomes. County units, including zero-population units, remain present. Post-warmup checkpoint summaries are diagnostic views of a subset of saved assignments; they never substitute for the complete 122,000-state convergence audit.

Among Texas counties above 500,000 population, the five largest baseline across-seed ranges in mean population fraction are:

| Texas county FIPS suffix | Population | Across-seed range in checkpoint mean population fraction |
| ------------------------ | ---------: | -------------------------------------------------------: |
| 491                      |    609,017 |                                                   0.3380 |
| 029                      |  2,009,324 |                                                   0.0992 |
| 453                      |  1,290,188 |                                                   0.0838 |
| 439                      |  2,110,640 |                                                   0.0745 |
| 201                      |  4,731,145 |                                                   0.0659 |

FIPS suffix 491 is Williamson County; its 0.3380 range is **33.8 percentage points**. Bexar (029), Travis (453), Tarrant (439), and Harris (201) also show differences. For Harris, the last-ten minus first-ten snapshot mean change ranges from +0.0091 to +0.1879 across baseline chains; Dallas includes changes in opposing directions. This locates persistent geographic and temporal behavior for subsequent investigation, without proving disconnected sampler support or statistical significance. Inspect [county/chain summaries](county_chain_summary.csv), [all county ranges](county_chain_ranges.csv), and [snapshot provenance](geography_audit.json). Full snapshot rows remain in the protected local audit directory.

## Data and method status

Texas retains all **668,757 blocks**, population **29,145,505**, and 9,712 simulation units. PLANC2333 remains scored at block resolution: **8 modeled Democratic-majority presidential districts**. The approved five ring repairs are candidate-only. Eight tiny precinct overlap pairs remain unresolved; adjacency comparisons agree for this candidate, which does not erase the geometry issue. Texas starting-map sensitivity beyond the prior-map initialization has not been established.

NC retains all **236,638 blocks**, population **10,439,388**, and the common **2,681 units** with both assignments, including the Onslow split. The approved block-union baseline has zero positive-area overlaps and exact agreement between GerryChain and shared-boundary adjacency. The precinct sensitivity has different geometry and a graph differing by 47 edges; it is never pooled with the primary graph. Each enacted NC plan scores **3 modeled Democratic-majority presidential districts**.

A supplemental [adopted-plan polygon audit](adopted_plan_geometry.json) found valid single polygons and no positive-area overlaps for all 38 Texas PLANC2333 districts and all 14 districts in each NC plan. Both NC polygon population fields match the official block master exactly. This establishes physical polygon connectedness, not independent equivalence of an enacted block-level adjacency graph or full legal compliance.

RDH modeled block votes are not observed block returns. Texas source/canvass deficits, NC privacy-noise/mixed-source differences, the one-vote NC block/precinct discrepancy and differing official return snapshots remain explicit in the source audit. No balancing correction was imposed. Enacted-plan alternative-election and uniform-swing sensitivities were evaluated; alternative-election scoring over every ensemble state remains unavailable.

The sampler uses uniform cut-edge choice, IID random-MST proposals, `node_repeats=2`, `max_attempts=1000`, pair reselection, population bounds, graph contiguity, and always-accept for valid proposals. It is not established as a uniform sampler over valid maps or a fully legally constrained ensemble. Reordering random-weight assignment for exact continuation defines a recorded new implementation lineage; it does not prove equivalence to legacy seeded trajectories. No descriptive frequency is presented as a calibrated p-value, and zero observations never imply zero probability.

## Verification and exact execution records

The [executed manifest](campaign_manifest.json) preserves all 26 command argument arrays, seeds, lengths, dataset hashes, source-code hashes, output namespaces and supplemental-registration history. Its [byte-exact original](campaign_manifest.original) matches the input-manifest SHA-256 recorded by the diagnostics and figures; publication JSON copies receive formatting without changing the protected originals. [Executed state registries](executed_state_registries.json) preserve all eight condition definitions. Original and failed manifests/logs/checkpoints remain local and unchanged. The corrected ten-chain sensitivity launch used the science interpreter after the initial system-interpreter attempt failed importing GeoPandas before any states were produced.

Both state-CLI research audits completed and exactly matched their experiment subsets in the full audit. The revised campaign planner prepares all 26 definitions; a separate no-simulation replay check matched all scientific settings to the executed manifest. CLI/launcher changes were made after the campaign ended. The sampler and checkpoint-helper hashes are unchanged and remain compatible with the completed runs.

Commands below ran from the repository root. Existing output paths now refuse collisions; use new paths to repeat them. Runtime caches and test fixtures are confined to project-local paths.

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
.venv/science/bin/python -m unittest discover -s tests -v
.venv/bin/uv pip check --python .venv/science/bin/python
```

The final full scientific suite passed **54 tests**, with no skips; see the [complete log](test_suite_final.log) and [final verification record](verification_final.json). Relevant real-data audits, final-checkpoint checks and exact Texas/NC continuation probes are separate evidence. Dependency consistency passed for all 27 pinned research packages. Changed supported files pass Prettier checks, 25 task Python files pass syntax checks, and Git whitespace checks pass. No Python formatter/linter is configured, so no lint or Python-formatting pass is claimed. The [final artifact manifest](artifact_manifest_final.json) records publication-file checksums. Earlier publication verification/manifest snapshots are retained; the final records include the subsequent tail supplement and completed report.

Expected scientific failures are preserved: both raw-source geometry validations returned exit 1; both states fail convergence screens. Earlier Python-3.9 import, unsigned-header download, continuation-probe and incorrect-interpreter sensitivity failures are documented. Default cache-location attempts also failed under filesystem restrictions; corrected commands use the project-local cache paths above. Passing execution and software tests does not change the scientific failure status.

## Next necessary research work

Investigate the observed geographic modes and transient cut-edge behavior with dispersed valid starting maps, particularly Texas, and documented proposal/constraint experiments that preserve their own target definitions. Continue compatible existing chains without discarding early runs, using exact version-2 continuation; establish a scientifically justified simulation budget and MCSE/stability acceptance criteria before treating additional length as a solution. Wider-tolerance results do not authorize a baseline change.

Resolve or bound the eight Texas source overlaps and source-election discrepancies, evaluate election-model uncertainty across the full ensemble, and document the legal/demographic constraints relevant to the research claim. An independent enacted block-graph contiguity/equivalence check and the unavailable historical-chain audit remain distinct tasks. Any failed, unavailable, skipped or nonfinite required diagnostic prevents research readiness. **No conference inference is certified by this deliverable.**
