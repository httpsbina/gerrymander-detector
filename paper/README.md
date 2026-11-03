# Paper outputs

I generate these files from the registered frozen analysis with:

```sh
python -m paper.export
```

I keep figures in `figures/`, tables in `tables/`, the NC findings in `nc_findings.md`, and every table and findings value in `results.json`, including the full-precision diagnostics and display values. `artifacts.json` records their checksums. The exporter calls the frozen `reproduce_paper.py` without changing it, checks regenerated figures against the freeze, and preserves existing state values when another frozen state is added.

I read the freeze registry at execution time, so the same command includes Texas once its frozen outputs are registered. Repeated exports stop if an existing figure, table, or state's numbers differ.

## Limitations

I export registered numerical freezes; the source and campaign reports retain the data and model limitations. Texas fixtures test the export contract, while its actual paper outputs await its freeze.
