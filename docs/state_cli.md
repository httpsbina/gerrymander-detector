# State-configured research CLI (Phase 1)

This is a **non-destructive orchestration layer** around the existing ReCom
runner (`src/chain/run_ensemble.py`) and independent-chain auditor
(`src/analysis/audit_ensemble_chains.py`). It does not replace either tool,
change historical results, download data, or certify convergence.

Run from the repository root using the existing virtual environment:

```powershell
.\.venv\Scripts\python.exe main.py --texas
.\.venv\Scripts\python.exe main.py --nc --year 2023
.\.venv\Scripts\python.exe main.py --nc --year 2025
.\.venv\Scripts\python.exe main.py --penn
```

With no `--stage`, all commands are **read-only status checks**. Pennsylvania
is explicitly **pending data preparation**. `--penn` does not currently fetch
or process Pennsylvania, and its simulation and audit stages refuse to run.

## Audit existing Texas and North Carolina ensembles

```powershell
.\.venv\Scripts\python.exe main.py --texas --stage audit --dry-run
.\.venv\Scripts\python.exe main.py --texas --stage audit
.\.venv\Scripts\python.exe main.py --nc --year 2023 --stage audit
.\.venv\Scripts\python.exe main.py --nc --year 2025 --stage audit
```

The audit uses the configured existing simulation files. Texas defaults to
three 4,000-state chains with 500 warmup states; NC uses three 5,000-state
chains per starting plan, with 500 warmup states. The current scripts do **not**
establish convergence, and this CLI does not claim otherwise.

## Explicit simulations

Simulations require both `--steps` and `--seed`. Use `--dry-run` to inspect the
full command without starting a simulation:

```powershell
.\.venv\Scripts\python.exe main.py --nc --year 2025 --stage simulate --steps 100 --seed 1234 --dry-run
```

To continue an existing Texas chain from the recorded step-4,000 checkpoint:

```powershell
.\.venv\Scripts\python.exe main.py --texas --stage simulate --steps 2000 --seed 1117 --resume-from outputs/analysis/tx_independent_pilot/checkpoints/texas_independent_pilot_checkpoint_eps0p001_seed1117_next4000.pkl --dry-run
```

Remove `--dry-run` only when ready to execute that simulation. The CLI refuses
to overwrite an existing chain CSV segment. It validates checkpoint names
against state, epsilon and seed; the existing runner performs the substantive
checkpoint checks.

For a clean restart, set `PYTHONHASHSEED` consistently with saved checkpoints.
The CLI supplies `PYTHONHASHSEED=0` to child processes if it is otherwise unset.

## Configuration and source limitations

`configs/states.json` is the state registry. It records validated local dataset
paths, per-plan starting-map column, election/population columns, tolerances,
reproducibility labels and existing audit defaults. It is intentionally JSON,
so there is no new YAML dependency.

- Texas's neutral ReCom ensemble starts from the prior congressional map.
  The 2025 PLANC2333 enacted benchmark must still be evaluated separately at
  Census-block level. Do not treat the `current` assignment as PLANC2333.
- North Carolina uses the same processed graph for 2023 and 2025 initializations;
  the two configured plan-year labels must not be collapsed into one.
- Pennsylvania has **no** validated input definition yet. A future data-source
  adapter and preprocessing/validation stages are separate implementation work.

The CLI only checks whether the configured dataset file exists before running
a simulation. The underlying runner handles graph and population validations.
Full election provenance, legal constraints, geography matching, and statistical
reliability remain scientific responsibilities, not guaranteed CLI features.

## No-GIS smoke tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The tests run without GerryChain, GeoPandas, or RDH access, and cover state/year
selection, command construction, pending-data blocking, no-execution dry runs,
and accidental overwrite protection.
