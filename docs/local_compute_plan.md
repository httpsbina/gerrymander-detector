# Local compute plan, November 2026

November 16 is the laptop transfer deadline. Results freeze only under the [baseline freeze rule](freeze_rule.md), with no calendar-based scientific stopping point. Runs continue on other available compute after transfer. All estimates below assume local compute; no cluster allocation is required.

## Measured capacity

Two timed waves used eight simultaneous, single-threaded processes: six North Carolina chains and two Texas chains, rotating the Texas pairs. Continuation, graph loading, and checkpoint I/O are included.

| State          | Slowest | Median | Fastest |
| -------------- | ------: | -----: | ------: |
| North Carolina |  23,389 | 25,393 |  28,956 |
| Texas          |   4,028 |  4,388 |   4,667 |

Rates are states per hour per chain. Eight simultaneous Texas chains have not yet been timed. Until then, reserve twice the measured Texas time: approximately 2,014 states per hour per chain.

## Current convergence screens

At 13,000 states per chain, the six-chain NC baseline has the following joint results after the existing 500-state warmup:

| Metric           | Rank-normalized split R-hat | Bulk ESS | Tail ESS |
| ---------------- | --------------------------: | -------: | -------: |
| Democratic seats |                     1.00338 |    1,191 |    1,876 |
| Efficiency gap   |                     1.00445 |      969 |    2,833 |
| Cut edges        |                     1.00683 |    1,463 |    3,795 |
| Mean–median      |                     1.00869 |    1,091 |    2,809 |

All four joint screens pass R-hat below 1.01 and bulk/tail ESS at least 600. The three-chain 2023 starting-map group still fails the mean–median R-hat screen. Continuation is running toward 18,000 states per chain; both starting-map groups must also pass their existing ESS threshold of 400.

The last completed Texas audit is at 6,400 states per chain:

| Metric           |   R-hat | Bulk ESS | Tail ESS | ESS-only projected states per chain |
| ---------------- | ------: | -------: | -------: | ----------------------------------: |
| Democratic seats | 1.02408 |      112 |      216 |                              21,545 |
| Efficiency gap   | 1.03027 |      114 |      293 |                              21,231 |
| Cut edges        | 1.05762 |       90 |      299 |                              26,664 |
| Mean–median      | 1.05058 |       80 |      229 |                              30,010 |

The Texas estimates extrapolate the smaller of bulk and tail ESS per retained state to the unchanged threshold of 400. R-hat has no reliable linear completion forecast.

## Schedule through November 16

1. **November 2–3:** continue NC until every joint and separate starting-map primary screen passes. Texas's original four chains continue alongside NC.
2. **November 3–6:** prepare four independent, population-balanced Texas starting maps and run those chains alongside the original four. Budget a first milestone of 50,000 states per chain. At half the slowest measured Texas rate this requires about 25 active compute hours for a new chain, or 3.1 days at eight compute hours per day. Initialization time is additional and will be measured.
3. **November 6–15:** reassess the existing screens at completed milestones and extend the same chains where needed. At eight active hours daily and the conservative rate, roughly 210,000 states per chain fit within the original November 2–16 budget. Update this estimate after measuring eight Texas chains together.
4. **Before November 16:** preserve a complete boundary snapshot, pinned environment, source fingerprints, seeds, configuration, chain segments, and matching checkpoints for transfer.

Checkpoints are written every 100 states. A transferable continuation boundary also requires its completed CSV segment; the highest checkpoint alone is insufficient. Runtime compatibility is strict: a checkpoint from this macOS Python environment cannot be assumed to resume exactly on Linux or a different Python build.

## Limitations

These are compute-budget estimates, not promised convergence dates. Every historical segment remains in its original experiment. New initialization groups require their own screening and a compatible joint audit; adding chains can increase the configured ESS requirement. Passing convergence screens does not resolve the existing Texas overlap audit or election-model limitations. Final results also require the configured Monte Carlo error, trace, window, warmup, and starting-map checks.

Machine-readable timings and full diagnostics are recorded under `outputs/analysis/convergence_campaign_2026-11-02/`, including `full_load_benchmark/throughput.json`, `local_capacity_estimate.json`, and `nc_primary_continuation/audit_001/diagnostics.json`.
