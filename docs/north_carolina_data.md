# North Carolina data and results

I compare the 2023 and 2025 congressional assignments on the same 2,681-unit Census-block-union geography, retaining 236,638 blocks and population 10,439,388. The modeled presidential totals are 2,713,609 Democratic votes and 2,896,942 Republican votes; both starting maps have 3 Democratic-majority districts.

I retain the Onslow split, including both assignment fields on the common units. The block-union graph has 7,581 edges and zero positive-area overlaps, while the precinct alternative differs by 47 edges. I analyze that alternative as a separate sensitivity condition.

## Frozen analysis

I ran three chains from each assignment and froze all six at 23,000 states per chain. After 500 warmup states per chain, I retained 135,000 states. The [findings list](../paper/nc_findings.md) gives every primary diagnostic by group; [paper/results.json](../paper/results.json) holds the full precision.

I reproduce the figures and tables with `python -m paper.export`. The [state CLI](state_cli.md) covers input validation, and the [source audit](../deliverables/rdh-research-audit-2026-11-02/README.md) records block accounting, election totals, geometry, and the Onslow split.

## Limitations

I use modeled block votes, and NC election sources include privacy noise and source-version differences. Block-to-precinct membership and the choice of geographic construction affect the experiment. The numerical freeze applies to this baseline, while the [earlier study](archive/north-carolina-methodology-before-rebuild.md) records a different run.
