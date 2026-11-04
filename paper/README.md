# Paper outputs

I generate the paper figures, tables and NC findings from registered frozen outputs with:

```sh
python -m paper.export
```

I write figures to `figures/`, tables to `tables/` and findings to `nc_findings.md`. `results.json` contains the full-precision diagnostics and displayed table and findings values; `artifacts.json` records the file checksums.

The exporter calls the frozen `reproduce_paper.py`, checks the regenerated figures against the freeze and reads the registry at execution time, so the same command includes Texas once its freeze is registered. I preserve existing state values when adding a freeze; repeated exports stop if a figure, table or state's numbers differ.

## Limitations

These files reproduce registered numerical freezes. The source and campaign reports retain the data and model limitations, while Texas fixtures check the export behavior; actual Texas paper outputs await its freeze.
