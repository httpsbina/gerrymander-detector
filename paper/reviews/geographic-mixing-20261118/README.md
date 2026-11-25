# Geographic mixing and simulation units

I checked the geographic scores on all retained saved assignments, while keeping the original sampler, thresholds and freezes unchanged. I separated chain drift from location aggregation and graph-count differences, rather than treating every difference as a mixing problem.

## Geographic convergence

Texas mean-distance R-hat is 1.0506 jointly, 1.0467 within baseline starts and 1.0482 within dispersed starts. The failure occurs within both starting cohorts, rather than only when the cohorts are pooled. Joint split R-hat is 1.0484, compared with folded R-hat 1.0060, which points mainly to location disagreement in the distributions. Mean-distance R-hat falls from 1.0540 at 65,000 states to 1.0506 at 70,000, while bulk ESS increases from 118.2 to 121.4; the complete trend includes reversals, so I do not extrapolate a passing chain length from it.

NC joint mean-distance R-hat is 1.0067, but bulk ESS is 516.4 against 600. The 2023 and 2025 initialization groups still have their own failed screens in the table. The earlier electoral freeze does not certify these additional geographic measurements.

| State | Cohort              | Measurement           | R-hat  | Bulk ESS | Tail ESS | ESS minimum |
| ----- | ------------------- | --------------------- | ------ | -------- | -------- | ----------- |
| NC    | joint               | normalized_rms_radius | 1.0053 | 589.7    | 837.7    | 600         |
| NC    | joint               | mean_distance_km      | 1.0067 | 516.4    | 788.4    | 600         |
| NC    | joint               | unit_centroid_mean_km | 1.0067 | 516.6    | 788.4    | 600         |
| NC    | nc_block_union_2023 | normalized_rms_radius | 1.0081 | 316.0    | 386.9    | 400         |
| NC    | nc_block_union_2023 | mean_distance_km      | 1.0117 | 218.7    | 418.9    | 400         |
| NC    | nc_block_union_2023 | unit_centroid_mean_km | 1.0117 | 219.1    | 418.9    | 400         |
| NC    | nc_block_union_2025 | normalized_rms_radius | 1.0031 | 277.1    | 457.7    | 400         |
| NC    | nc_block_union_2025 | mean_distance_km      | 1.0063 | 243.9    | 394.1    | 400         |
| NC    | nc_block_union_2025 | unit_centroid_mean_km | 1.0063 | 243.9    | 397.8    | 400         |
| TX    | joint               | normalized_rms_radius | 1.0418 | 162.2    | 775.7    | 800         |
| TX    | joint               | mean_distance_km      | 1.0506 | 121.4    | 805.9    | 800         |
| TX    | joint               | unit_centroid_mean_km | 1.0506 | 121.4    | 805.9    | 800         |
| TX    | tx_dispersed        | normalized_rms_radius | 1.0423 | 82.5     | 414.3    | 400         |
| TX    | tx_dispersed        | mean_distance_km      | 1.0482 | 68.0     | 551.3    | 400         |
| TX    | tx_dispersed        | unit_centroid_mean_km | 1.0482 | 68.0     | 551.3    | 400         |
| TX    | tx_rebuild          | normalized_rms_radius | 1.0364 | 112.9    | 387.6    | 400         |
| TX    | tx_rebuild          | mean_distance_km      | 1.0467 | 80.5     | 358.0    | 400         |
| TX    | tx_rebuild          | unit_centroid_mean_km | 1.0467 | 80.4     | 358.0    | 400         |

I use the full cohorts for these screens. The leave-one-out table identifies chains that contribute to disagreement, but those exploratory subsets do not replace any result or threshold. The diagnostic trends retain every 5,000-state prefix and NC’s final 23,000-state prefix; they do not create new frozen audits.

The following cases have flat or decreasing bulk or tail ESS in the final two prefixes; successive_audit_changes.csv retains every case, including increases. Reciprocal CV and centroid approximations repeat related information rather than independent evidence.

| State | Cohort              | Measure                    | Previous bulk ESS | Current bulk ESS | Previous tail ESS | Current tail ESS |
| ----- | ------------------- | -------------------------- | ----------------- | ---------------- | ----------------- | ---------------- |
| NC    | joint               | distance_cv                | 621.9             | 744.9            | 979.3             | 967.2            |
| NC    | joint               | inverse_distance_cv        | 621.9             | 744.9            | 979.3             | 967.2            |
| NC    | nc_block_union_2023 | atom_centroid_mean_km      | 248.9             | 219.1            | 381.6             | 418.9            |
| NC    | nc_block_union_2023 | mean_distance_km           | 248.8             | 218.7            | 381.6             | 418.9            |
| NC    | nc_block_union_2023 | unit_centroid_mean_km      | 248.9             | 219.1            | 381.6             | 418.9            |
| TX    | joint               | mean_district_cv           | 482.7             | 467.6            | 2109.1            | 2112.1           |
| TX    | tx_dispersed        | area_normalized_rms_radius | 300.4             | 285.6            | 1019.8            | 1106.8           |
| TX    | tx_dispersed        | silhouette                 | 413.6             | 340.8            | 1302.7            | 1354.4           |
| TX    | tx_rebuild          | atom_centroid_mean_km      | 97.8              | 80.5             | 281.0             | 358.0            |
| TX    | tx_rebuild          | distance_cv                | 333.7             | 332.6            | 242.8             | 282.1            |
| TX    | tx_rebuild          | inverse_distance_cv        | 333.7             | 332.6            | 242.8             | 282.1            |
| TX    | tx_rebuild          | mean_distance_km           | 97.8              | 80.5             | 281.0             | 358.0            |
| TX    | tx_rebuild          | normalized_rms_radius      | 114.6             | 112.9            | 329.8             | 387.6            |
| TX    | tx_rebuild          | sd_distance_km             | 131.6             | 130.6            | 267.4             | 309.3            |
| TX    | tx_rebuild          | unit_centroid_mean_km      | 97.8              | 80.4             | 281.0             | 358.0            |

## Chain movement

Texas seed 2227 has the largest absolute mean-distance half shift, +1.711 km. Omitting any one Texas chain leaves joint mean-distance R-hat at or above 1.0363; no single omission resolves the disagreement, and every chain remains in the reported ensemble.

| State | Cohort              | Seed  | Full mean, km | First-half mean, km | Second-half mean, km | Shift, km | Lag-1 checkpoint correlation |
| ----- | ------------------- | ----- | ------------- | ------------------- | -------------------- | --------- | ---------------------------- |
| NC    | nc_block_union_2023 | 707   | 34.528        | 34.502              | 34.554               | +0.052    | 0.384                        |
| NC    | nc_block_union_2023 | 808   | 34.583        | 34.430              | 34.735               | +0.305    | 0.103                        |
| NC    | nc_block_union_2023 | 909   | 34.955        | 35.134              | 34.777               | -0.357    | 0.274                        |
| NC    | nc_block_union_2025 | 1707  | 34.783        | 34.800              | 34.767               | -0.033    | 0.357                        |
| NC    | nc_block_union_2025 | 1808  | 34.652        | 34.744              | 34.561               | -0.183    | 0.360                        |
| NC    | nc_block_union_2025 | 1909  | 34.994        | 35.094              | 34.896               | -0.197    | 0.322                        |
| TX    | tx_dispersed        | 10007 | 37.889        | 37.743              | 38.035               | +0.292    | 0.740                        |
| TX    | tx_dispersed        | 10009 | 38.515        | 38.740              | 38.290               | -0.450    | 0.615                        |
| TX    | tx_dispersed        | 10037 | 37.669        | 37.261              | 38.077               | +0.816    | 0.607                        |
| TX    | tx_dispersed        | 10039 | 38.354        | 38.661              | 38.047               | -0.614    | 0.622                        |
| TX    | tx_rebuild          | 1117  | 37.611        | 37.670              | 37.552               | -0.117    | 0.601                        |
| TX    | tx_rebuild          | 2227  | 37.981        | 37.124              | 38.835               | +1.711    | 0.731                        |
| TX    | tx_rebuild          | 3331  | 37.600        | 37.526              | 37.673               | +0.148    | 0.674                        |
| TX    | tx_rebuild          | 4441  | 37.878        | 37.949              | 37.807               | -0.143    | 0.599                        |

The county records add to mean squared normalized RMS radius, not to mean distance or to the square of mean radius. Each county-window change therefore identifies where squared dispersion changes geographically, without attributing a cause to an individual boundary move.

| State | Cohort              | Seed  | Squared-radius half shift | Five largest absolute county changes                                                                      |
| ----- | ------------------- | ----- | ------------------------- | --------------------------------------------------------------------------------------------------------- |
| NC    | nc_block_union_2023 | 707   | +0.000859                 | JOHNSTON +0.000566; NEW HANOVER +0.000478; CUMBERLAND +0.000418; CARTERET -0.000260; ROCKINGHAM -0.000256 |
| NC    | nc_block_union_2023 | 808   | +0.001173                 | CUMBERLAND +0.000556; FORSYTH +0.000494; JOHNSTON -0.000457; BRUNSWICK +0.000358; UNION +0.000304         |
| NC    | nc_block_union_2023 | 909   | -0.001226                 | CUMBERLAND -0.000574; NEW HANOVER -0.000494; ONSLOW +0.000431; ROBESON -0.000381; WAYNE +0.000261         |
| NC    | nc_block_union_2025 | 1707  | +0.000165                 | CUMBERLAND +0.000496; NEW HANOVER +0.000463; ROBESON +0.000426; RANDOLPH +0.000396; CARTERET -0.000386    |
| NC    | nc_block_union_2025 | 1808  | -0.001224                 | NEW HANOVER -0.000932; CARTERET +0.000377; COLUMBUS +0.000373; PENDER -0.000325; UNION +0.000303          |
| NC    | nc_block_union_2025 | 1909  | -0.000341                 | UNION -0.000531; BRUNSWICK -0.000430; CUMBERLAND -0.000353; WAYNE -0.000335; FORSYTH +0.000286            |
| TX    | tx_dispersed        | 10007 | +0.000822                 | Webb +0.000495; Val Verde -0.000410; El Paso +0.000342; Nueces -0.000270; Taylor +0.000249                |
| TX    | tx_dispersed        | 10009 | -0.002280                 | Webb -0.001791; Taylor -0.000506; Val Verde +0.000414; Bexar +0.000371; Wichita +0.000312                 |
| TX    | tx_dispersed        | 10037 | +0.001665                 | El Paso +0.000295; Bexar +0.000261; Taylor +0.000190; Tom Green -0.000188; Webb +0.000173                 |
| TX    | tx_dispersed        | 10039 | -0.002444                 | El Paso -0.000940; Taylor -0.000719; Val Verde +0.000529; Webb -0.000524; Nueces -0.000220                |
| TX    | tx_rebuild          | 1117  | -0.000295                 | Taylor +0.000158; Wichita -0.000094; Val Verde -0.000086; Bell -0.000084; Medina +0.000082                |
| TX    | tx_rebuild          | 2227  | +0.004510                 | El Paso +0.000846; Webb +0.000701; Taylor +0.000631; Wichita -0.000226; Bell +0.000187                    |
| TX    | tx_rebuild          | 3331  | +0.001020                 | Webb +0.001058; El Paso +0.000642; Val Verde -0.000301; Nueces -0.000283; Taylor +0.000274                |
| TX    | tx_rebuild          | 4441  | -0.000604                 | Tom Green -0.000429; Wichita +0.000366; Val Verde +0.000354; Taylor -0.000339; Maverick +0.000334         |

I separately recomputed block-level mean distance in each chain’s largest adjacent-window shift and decomposed that change by county. These contributions sum to the actual change in statewide mean distance, in kilometres; the selected windows are exploratory cases from every chain, rather than a subset used for convergence. NC’s final window is shorter, with its endpoints and counts recorded.

| State | Seed  | From window   | To window     | Mean shift, km | Three largest absolute county contributions, km       |
| ----- | ----- | ------------- | ------------- | -------------- | ----------------------------------------------------- |
| NC    | 707   | 500–5,000     | 5,000–10,000  | -0.668         | CUMBERLAND -0.252; FORSYTH -0.198; UNION -0.132       |
| NC    | 808   | 15,000–20,000 | 20,000–23,000 | +1.289         | UNION +0.299; CUMBERLAND +0.236; NEW HANOVER +0.198   |
| NC    | 909   | 15,000–20,000 | 20,000–23,000 | -0.445         | NEW HANOVER -0.255; FORSYTH +0.205; CUMBERLAND -0.193 |
| NC    | 1707  | 5,000–10,000  | 10,000–15,000 | -1.109         | UNION -0.159; CUMBERLAND -0.152; DURHAM -0.138        |
| NC    | 1808  | 500–5,000     | 5,000–10,000  | -0.852         | WAKE -0.186; BRUNSWICK -0.124; NEW HANOVER -0.113     |
| NC    | 1909  | 500–5,000     | 5,000–10,000  | -0.510         | NEW HANOVER +0.238; UNION -0.211; FORSYTH -0.166      |
| TX    | 10007 | 55,000–60,000 | 60,000–65,000 | +2.563         | Ector +0.348; Midland +0.273; Travis +0.196           |
| TX    | 10009 | 55,000–60,000 | 60,000–65,000 | -1.934         | Fort Bend -0.403; McLennan -0.237; Bexar -0.222       |
| TX    | 10037 | 30,000–35,000 | 35,000–40,000 | +1.822         | Bell +0.211; Taylor +0.195; Harris -0.179             |
| TX    | 10039 | 45,000–50,000 | 50,000–55,000 | -1.283         | Bexar -0.378; Hidalgo +0.291; Nueces -0.218           |
| TX    | 1117  | 50,000–55,000 | 55,000–60,000 | +1.612         | Nueces +0.444; Bexar -0.376; Webb -0.287              |
| TX    | 2227  | 50,000–55,000 | 55,000–60,000 | -2.494         | Webb -0.311; Bell -0.257; Denton -0.240               |
| TX    | 3331  | 40,000–45,000 | 45,000–50,000 | -2.226         | Ector -0.370; Webb -0.363; El Paso -0.344             |
| TX    | 4441  | 10,000–15,000 | 15,000–20,000 | +1.954         | Webb +0.477; Bexar -0.356; El Paso +0.263             |

## Simulation units and measurement

The distinct measured unit-pair graph matches the native sampler graph exactly for each state and starting cohort. Texas has additional atomic edges because the same unit pair can share more than one atom-to-atom boundary; NC has no such multiplicity. There are no unmatched unit pairs to repair in this comparison.

| State | Cohort              | Native edges | Distinct measurement unit pairs | Measurement-only pairs | Native-only pairs | Extra atomic edges between units |
| ----- | ------------------- | ------------ | ------------------------------- | ---------------------- | ----------------- | -------------------------------- |
| NC    | nc_block_union_2023 | 7581         | 7581                            | 0                      | 0                 | 0                                |
| NC    | nc_block_union_2025 | 7581         | 7581                            | 0                      | 0                 | 0                                |
| TX    | tx_rebuild          | 26860        | 26860                           | 0                      | 0                 | 700                              |
| TX    | tx_dispersed        | 26860        | 26860                           | 0                      | 0                 | 700                              |

For every sampled map, I checked: atomic cut count = native cut count + atomic multiplicity excess + measurement-only cuts - native-only cuts. Counting each measured unit pair once removes atomic multiplicity from the comparison, while physical boundary length remains a separate quantity. The edge-difference table retains both endpoints and shared lengths; it does not alter adjacency.

| State | Maximum unit-centroid mean underestimate, km | Within-unit variance, km² | Across-chain mean range, km |
| ----- | -------------------------------------------- | ------------------------- | --------------------------- |
| NC    | 0.0727                                       | 6.6813                    | 0.4661                      |
| TX    | 0.0398                                       | 4.6269                    | 0.9152                      |

I also checked block RMS² = unit-centroid RMS² + within-unit variance on every saved map. The within-unit term is fixed across sampled whole-unit plans, so subtracting it cannot explain chain disagreement in squared RMS. Mean distance has a different, nonlinear aggregation error, which I measure separately. The block-level scores remain the primary values.

| Map             | Split simulation units | Population in split units | Block mean distance, km | Atomic-centroid mean distance, km |
| --------------- | ---------------------- | ------------------------- | ----------------------- | --------------------------------- |
| NC enacted_2023 | 0                      | 0                         | 41.1857                 | 41.1324                           |
| NC enacted_2025 | 0                      | 0                         | 41.8045                 | 41.7506                           |
| TX enacted_2025 | 427                    | 1,782,927                 | 52.8458                 | 52.8161                           |

I retain Texas’s enacted block assignments wherever they split simulation units. I do not assign a split unit to its majority district or present that altered map as PLANC2333.

| Map     | Minimum population relabeling for whole units | Within-unit boundary, km | Distinct unit pairs with any cut | Pairs with cut and uncut contacts |
| ------- | --------------------------------------------- | ------------------------ | -------------------------------- | --------------------------------- |
| NC 2023 | 0                                             | 0.000                    | 779                              | 0                                 |
| NC 2025 | 0                                             | 0.000                    | 761                              | 0                                 |
| TX 2025 | 205,327                                       | 929.241                  | 2949                             | 538                               |

Minimum relabeling is only a combinatorial lower bound on the population whose district would need to change if each unit had one label; it does not construct a balanced or contiguous map. A split unit can have both cut and uncut contacts with its neighbor, so even an any-cut unit-pair count does not turn Texas’s enacted assignment into a native sampler plan.

| Map     | Any-cut unit pairs | Reference median | Reference states at or above enacted | Reference checkpoints |
| ------- | ------------------ | ---------------- | ------------------------------------ | --------------------- |
| NC 2023 | 779                | 731.0            | 171                                  | 1350                  |
| NC 2025 | 761                | 731.0            | 321                                  | 1350                  |
| TX 2025 | 2949               | 2669.0           | 4                                    | 5560                  |

## Changes that preserve the experiment

I now report native graph cuts, distinct measured unit-pair cuts, atomic multiplicity and physical boundary length separately, while retaining block-level population distances. These are reporting and measurement distinctions; the saved plans and original cut-edge scores stay intact.

Additional mixing would require a separately recorded continuation with the same kernel and constraints, retaining every original chain and starting-map cohort. More independent chains can improve exploration, but they do not guarantee that the existing slow chains have mixed. I have not started new simulations or altered the frozen results.

## Limitations

The geographic screens still have failures, so the reference ranks remain preliminary. Only saved 100-state assignments are available for these geographic calculations; checkpoint autocorrelation lags are not single ReCom steps. County contributions locate changes in mean distance and squared dispersion, without identifying a causal boundary move. Simulation units restrict which plans can be represented, while the Texas enacted map splits some of them; measurement changes cannot remove that support mismatch. The original Texas graph retains its overlap warnings, and changing that graph would change the experiment. Counts and ranks are descriptive rather than calibrated probabilities or evidence of intent.

## Records

results.json records input checksums and exact decomposition counts; diagnostic_trends.csv, chain_windows.csv and county_window_changes.csv retain every comparison. All chains and saved observations remain included. The verification record includes the executed commands, test results and unchanged sampler/checkpoint hashes.
