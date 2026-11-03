# Research workflow

I compare congressional assignments with ReCom ensembles, using the same data and constraints within each experiment. NC is frozen at `nc-baseline-23000`; Texas continues with the original baseline cohort and four dispersed starts.

## Data and runs

I validate block IDs, coverage, totals, geometry, adjacency, assignments, and contiguity before simulation. Texas PLANC2333 stays at Census-block resolution, while NC's two assignments share the block-union geography described in the [source audit](../deliverables/rdh-research-audit-2026-11-02/README.md).

I added the fourth Texas seed before diagnostic review, population-sensitivity runs after the first low-ESS NC results, and four dispersed Texas starts during continuation.

I keep every chain and recorded segment, with seeds, commands, software versions, and checksums in the execution records. The [state CLI guide](state_cli.md) lists the commands; the [continuation record](continuation.md) covers transfer and replay.

## Freeze and paper outputs

I freeze a state only when every primary metric passes jointly and within each starting-map group, following the [recorded rule](freeze_rule.md). A date or simulation budget never substitutes for that screen.

I regenerate the registered frozen results and export the paper layout with:

```sh
python -m paper.export
```

The exporter calls the unchanged frozen reproducer, writes figures under `paper/figures`, tables under `paper/tables`, and numbers under `paper/results.json`. It reads the freeze registry, so Texas is included when its freeze is registered. It checks existing artifacts before writing and stops if an existing state's numbers or figures differ.

## Limitations

I use modeled election allocations and the implemented population and contiguity constraints; these ensembles carry no claim of uniform sampling or full legal compliance. The source and campaign reports record the geographic and election-model uncertainties for each experiment.
