# Checkpoint election sensitivity

I scored the saved assignments with every other statewide Democratic-versus-Republican contest in the local 2024 block files, including judicial elections. I also rescored the presidential vote as a check against the chain CSVs. I kept the original vote magnitudes, with no statewide normalization or uniform swing.

I used Texas's shared 45,000-state history and NC's frozen 23,000-state history, scoring every checkpoint saved at a 100-state boundary after the existing warmup. A checkpoint at next step N contains recorded state N-1. I count checkpoint observations, including revisited assignments, rather than distinct maps.

## Texas

| Election                   | Mean Democratic seats | Enacted year | Enacted seats | At or below enacted | Checkpoints |
| -------------------------- | --------------------: | ------------ | ------------: | ------------------: | ----------: |
| President                  |              12.86096 | 2025         |             8 |                   1 |        3560 |
| US Senate                  |              17.21910 | 2025         |             8 |                   0 |        3560 |
| Criminal appeals 7         |              13.11208 | 2025         |             8 |                   0 |        3560 |
| Criminal appeals 8         |              12.07079 | 2025         |             8 |                  20 |        3560 |
| Criminal appeals presiding |              13.09185 | 2025         |             8 |                   1 |        3560 |
| Railroad commissioner      |              12.98764 | 2025         |             8 |                   2 |        3560 |
| Supreme Court 2            |              13.08483 | 2025         |             8 |                   1 |        3560 |
| Supreme Court 4            |              14.09803 | 2025         |             8 |                   0 |        3560 |
| Supreme Court 6            |              13.31601 | 2025         |             8 |                   1 |        3560 |

## North Carolina

| Election                          | Mean Democratic seats | Enacted year | Enacted seats | At or below enacted | Checkpoints |
| --------------------------------- | --------------------: | ------------ | ------------: | ------------------: | ----------: |
| President                         |               5.35037 | 2023         |             3 |                   7 |        1350 |
| President                         |               5.35037 | 2025         |             3 |                   7 |        1350 |
| Attorney general                  |               6.49111 | 2023         |             4 |                   8 |        1350 |
| Attorney general                  |               6.49111 | 2025         |             3 |                   0 |        1350 |
| Auditor                           |               5.62963 | 2023         |             3 |                   3 |        1350 |
| Auditor                           |               5.62963 | 2025         |             3 |                   3 |        1350 |
| Agriculture commissioner          |               4.30296 | 2023         |             3 |                 225 |        1350 |
| Agriculture commissioner          |               4.30296 | 2025         |             3 |                 225 |        1350 |
| Insurance commissioner            |               5.09259 | 2023         |             3 |                  25 |        1350 |
| Insurance commissioner            |               5.09259 | 2025         |             3 |                  25 |        1350 |
| Labor commissioner                |               4.93259 | 2023         |             3 |                  46 |        1350 |
| Labor commissioner                |               4.93259 | 2025         |             3 |                  46 |        1350 |
| Governor                          |              11.22222 | 2023         |            12 |                1258 |        1350 |
| Governor                          |              11.22222 | 2025         |            13 |                1350 |        1350 |
| Lieutenant governor               |               6.49185 | 2023         |             4 |                  14 |        1350 |
| Lieutenant governor               |               6.49185 | 2025         |             3 |                   0 |        1350 |
| Secretary of state                |               6.78148 | 2023         |             4 |                   6 |        1350 |
| Secretary of state                |               6.78148 | 2025         |             3 |                   0 |        1350 |
| Public instruction superintendent |               6.50370 | 2023         |             4 |                   8 |        1350 |
| Public instruction superintendent |               6.50370 | 2025         |             3 |                   0 |        1350 |
| Treasurer                         |               5.05185 | 2023         |             3 |                  32 |        1350 |
| Treasurer                         |               5.05185 | 2025         |             3 |                  32 |        1350 |
| Appeals court 12                  |               5.59630 | 2023         |             3 |                   3 |        1350 |
| Appeals court 12                  |               5.59630 | 2025         |             3 |                   3 |        1350 |
| Appeals court 14                  |               5.12148 | 2023         |             3 |                  21 |        1350 |
| Appeals court 14                  |               5.12148 | 2025         |             3 |                  21 |        1350 |
| Appeals court 15                  |               5.27556 | 2023         |             3 |                  13 |        1350 |
| Appeals court 15                  |               5.27556 | 2025         |             3 |                  13 |        1350 |
| Supreme Court 6                   |               5.94074 | 2023         |             4 |                  61 |        1350 |
| Supreme Court 6                   |               5.94074 | 2025         |             3 |                   2 |        1350 |

## Reproducing

```sh
nice -n 15 env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 .venv/science/bin/python -m paper.score_checkpoint_elections --source-root . --output-dir paper/NEW_ELECTION_DIRECTORY
nice -n 15 env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 .venv/science/bin/python -m paper.validate_checkpoint_elections --source-root . --results paper/NEW_ELECTION_DIRECTORY/results.json
nice -n 15 .venv/science/bin/python -m paper.summarize_checkpoint_elections --results paper/NEW_ELECTION_DIRECTORY/results.json
```

`results.json` contains the block coverage, statewide totals, cohort and chain summaries, seeds, source hashes and checkpoint hashes. `checkpoint_scores.json` records every scored assignment. `summary.csv` and `summary.json` contain both cohort and joint comparisons. `assignment_validation.json` checks the graph, checkpoint provenance and plan fingerprints against the simulation inputs. I score Texas PLANC2333 and both NC enacted plans directly from their block assignments.

## Limitations

I use RDH's modeled block allocations, and these scores inherit their precinct membership and allocation uncertainty. The eight previously recorded Texas precinct overlap pairs remain unresolved. Democratic seats mean strict Democratic majorities of the two-party vote; third-party votes are excluded. The checkpoints are autocorrelated, so the counts are descriptive frequencies, with zero observations leaving nonzero probabilities possible. Texas still fails its convergence screens, and the NC freeze covers the original presidential metrics rather than these additional election scores. The implemented ReCom ensemble is not established as uniform or fully legally constrained. I exclude district-only races and NC's nonpartisan referendum because they do not provide statewide Democratic-versus-Republican votes.
