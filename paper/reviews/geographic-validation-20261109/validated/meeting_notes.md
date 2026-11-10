# Geographic results

I compared the enacted maps with all retained saved checkpoints, using no vote or party fields: 5,560 Texas states and 1,350 NC states. Each checkpoint is 100 chain states apart.

| Map        | Silhouette, enacted / median | Population radius, enacted / median | Perimeter compactness, enacted / median |
| ---------- | ---------------------------: | ----------------------------------: | --------------------------------------: |
| Texas 2025 |              0.0248 / 0.1495 |                     0.2755 / 0.1988 |                         0.2220 / 0.1562 |
| NC 2023    |              0.1269 / 0.1949 |                     0.3327 / 0.2894 |                         0.2442 / 0.1893 |
| NC 2025    |              0.1220 / 0.1949 |                     0.3374 / 0.2894 |                         0.2495 / 0.1893 |

Higher silhouette means better geographic separation; higher radius means more population dispersion; higher perimeter compactness means a shorter boundary relative to area.

Texas has lower silhouette and higher radius than every retained checkpoint. For NC, 4 checkpoints fall at or below the 2023 silhouette and 4 at or below the 2025 silhouette; 4 checkpoints are at least as dispersed as the 2023 map, and 1 at least as dispersed as the 2025 map. All three enacted maps have higher mean perimeter compactness than every retained checkpoint, though.

The low silhouette ordering holds in the ten-checkpoint-per-chain pilot across four population-sample seeds, both sample sizes and projected versus geodesic distances. Radius uses every Census block’s population and centroid, and perimeter uses the same block-derived measurement geography for enacted and simulated maps.

## Limitations

The new geographic metrics do not all meet the original numerical reference screens. Texas joint radius R-hat is 1.0418, with bulk ESS 162.2; the NC joint radius bulk ESS is 589.7 against a 600 reference. Mean perimeter compactness passes every cohort and joint reference screen, while silhouette or radius fails one or more screens in each state. These are preliminary geographic comparisons within the constrained ensemble, rather than a probability of gerrymandering. I have kept the original freezes unchanged.

## Records

The figures are geographic_comparison.png, enacted_geography.png and geographic_traces.png; chain_means.csv records each chain’s mean and half-history shift. meeting_table.csv contains the enacted values, simulated quantiles and both directional counts; diagnostics.csv and reference_screens.csv contain every cohort and joint screen. results.json, sample_sensitivity.csv and verification.json retain the calculations and checks.
