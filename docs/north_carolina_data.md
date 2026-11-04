# North Carolina data and results

I compare the 2023 and 2025 assignments on the same 2,681-unit Census-block-union geography, which retains 236,638 blocks and population 10,439,388. Both starting maps produce 3 Democratic-majority districts from modeled presidential totals of 2,713,609 Democratic and 2,896,942 Republican votes.

The common units retain both assignments and the Onslow split. I obtain 7,581 graph edges and zero positive-area overlaps from the block unions; the precinct-based graph differs by 47 edges, so I keep it as a separate sensitivity experiment.

## Frozen baseline

I ran three chains from each assignment and froze all six at 23,000 states per chain. Removing the first 500 states of each chain leaves 135,000 retained states. The [NC findings](../paper/nc_findings.md) show every primary diagnostic by group, with full precision in [paper/results.json](../paper/results.json).

## Reproducing

I regenerate the figures and tables with `python -m paper.export`. The [state CLI guide](state_cli.md) gives the input-validation commands, and the [source report](../deliverables/rdh-research-audit-2026-11-02/README.md) records the block accounting, election totals, geometry and Onslow construction. I keep the [earlier NC study](archive/north-carolina-methodology-before-rebuild.md) separate from this baseline.

## Limitations

The block votes are modeled, and the election sources contain privacy noise and source-version differences. Geographic construction also depends on RDH's block-to-precinct membership. The numerical freeze applies to this baseline and its recorded inputs.
