# Research workflow

I compare enacted congressional assignments with ReCom samples, keeping the geographic inputs and constraints fixed within each experiment. NC is frozen at `nc-baseline-23000`; I am continuing the four original Texas chains and four dispersed-start chains.

## Data and sampling

I check block IDs and coverage, population and election totals, geometry, adjacency, assignments and contiguity before sampling. I score Texas PLANC2333 at block resolution and use one block-union geography for both NC assignments, as recorded in the [source report](../deliverables/rdh-research-audit-2026-11-02/README.md).

I added the fourth Texas seed before diagnostic review, population-sensitivity chains after the first low-ESS NC results, and four dispersed Texas starts during continuation.

I retain every recorded segment and chain, with seeds, commands, versions and checksums in the run records. The [state CLI guide](state_cli.md) gives the execution commands, while the [continuation record](continuation.md) describes transfer and replay.

## Freeze and paper export

I freeze a state when every primary metric passes jointly and within each starting-map group under the [recorded rule](freeze_rule.md). I use the convergence screens as the stopping condition, regardless of the date or simulation budget.

```sh
python -m paper.export
```

I use this command to call the frozen reproducer and write figures to `paper/figures`, tables to `paper/tables` and values to `paper/results.json`. The exporter reads the freeze registry, so it includes Texas when its freeze is registered; it stops if an existing state's numbers or figures differ.

## Limitations

I use modeled election allocations with population and graph-contiguity constraints. I have not established sampler uniformity or full legal compliance; geographic and election-model uncertainties remain in the source and campaign reports.
