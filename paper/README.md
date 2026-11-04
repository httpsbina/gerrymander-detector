# Paper outputs

I generate the paper figures, tables and state findings from registered frozen outputs with:

```sh
python -m paper.export
```

I write figures to `figures/`, tables to `tables/` and findings to `nc_findings.md` and `texas_findings.md`. `results.json` contains the full-precision diagnostics and displayed table and findings values; `artifacts.json` records the file checksums.

The exporter calls the frozen `reproduce_paper.py`, checks the regenerated figures against the freeze and reads the registry at execution time, so the same command includes both frozen states. I preserve existing state values when adding a freeze; repeated exports stop if a figure, table or state's numbers differ.

## Limitations

I export both registered primary numerical freezes; the freeze records retain the unresolved MCSE and window-stability acceptance criteria, data uncertainties and model limitations.
