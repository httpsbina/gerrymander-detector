# Provisional Texas outputs

I generated these figures and tables from the checksum-registered shared audit in `paper/texas_audits.json`. Every plotted or tabulated value is in `results.json`, with source fingerprints.

## Reproducing

```sh
nice -n 15 env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 MPLCONFIGDIR="$PWD/.venv/matplotlib" .venv/science/bin/python -m paper.export --texas
```

I use the same command after Texas freezes; it reads the freeze registry and writes the registered analysis under `paper/figures` and `paper/tables`. I preserve existing outputs and stop if a repeated export differs.

## Limitations

This shared-prefix comparison is provisional. I retain the extra baseline states in the running chains, and the findings file records the model and inference limitations.
