Gerrymander Detector: executable Texas/NC preflight deliverable
November 2, 2026

What is delivered
-----------------
A standard-library CLI stage, --stage preflight, and three actual reports from
this checkout: Texas, NC 2023, and NC 2025. Each report directory contains a
human-readable report.txt and machine-readable report.json.

Run from the repository root:

python3 main.py --texas --stage preflight
python3 main.py --nc --year 2023 --stage preflight
python3 main.py --nc --year 2025 --stage preflight

These commands print JSON to stdout. To save a report, choose a NEW directory:

python3 main.py --texas --stage preflight --report-dir deliverables/my-new-tx-audit

The destination must resolve inside this checkout. Existing directories,
including empty ones, are refused. --dry-run prints the destination without
inspecting inputs, writing files, or starting subprocesses. Preflight rejects
simulation/audit overrides, because it inventories configured experiments and
any additional seeds found with the same prefix and tolerance.

Evidence recorded
-----------------
- Configuration snapshot, explicit seed lists, actual command, Git branch/commit,
  dirty working-tree status, interpreter/platform and dependency versions.
- SHA-256 and byte size for existing dataset, registry, CLI, sampler, auditor,
  chain CSVs and checkpoint files within the configured scope.
- Actual per-seed CSV step ranges and integrity results. Every matching segment
  is considered; configured target lengths never truncate the inventory.
- Missing columns, wrong filenames, row-count mismatches, gaps, overlapping
  steps, seed/tolerance mismatches, nonfinite diagnostic values, invalid seat
  and cut-edge counts, population tolerance violations and malformed plan hashes.
- Explicit unavailable statuses for every required scientific diagnostic,
  including MCSE, warmup/starting-map sensitivity and joint NC assessment.

Checkpoint files are hashed only, never unpickled. A hash does not verify runtime
compatibility, graph identity, or reproducible continuation. Passing CSV integrity
cannot establish convergence, valid geography, correct source data or readiness.
This stage always reports research_ready=false; it does not implement or replace
the scientific diagnostics needed to establish readiness.

Actual results in this delivery
-------------------------------
Texas: dataset absent; no segments for configured seeds 1117, 2227, 3331.
NC 2023: dataset absent; no segments for configured seeds 707, 808, 909.
NC 2025: dataset absent; no segments for configured seeds 707, 808, 909.
No checkpoints were found at the configured paths. Verified chain lengths,
R-hat, bulk/tail ESS, MCSE, overlap resolution, block coverage and contiguity
are unavailable. Execution completed for all three reports. Neither state is
research-ready. These reports are evidence of missing inputs in this checkout,
not evidence that historical chains never existed.

Texas PLANC2333 remains a separate block-resolution benchmark. NC's two starting
maps remain separate configurations. Modeled block votes are not observed block
returns, and ReCom is not established as a uniform or fully legally constrained
ensemble. No frequencies or probabilities were estimated.

Verification commands
---------------------
Temporary test fixtures were confined to tests/runtime inside the checkout:

mkdir -p tests/runtime
TMPDIR="$PWD/tests/runtime" PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v

The full suite passed: 28 tests, including nine new integrity/CLI tests. Fixtures
and mocked connectors are not real-data scientific evidence.

The three report-generation commands actually executed were:

python3 main.py --texas --stage preflight --report-dir deliverables/tx-preflight-2026-11-02
python3 main.py --nc --year 2023 --stage preflight --report-dir deliverables/nc-2023-preflight-2026-11-02
python3 main.py --nc --year 2025 --stage preflight --report-dir deliverables/nc-2025-preflight-2026-11-02

Each used PYTHONDONTWRITEBYTECODE=1. Repeating the first command was checked to
return exit 2 on the existing directory, preserving the report bytes.

Python source was parsed with ast.parse and git diff --check passed. No Python
formatter/linter is configured in the repository or available in the inspected
environment. No Prettier executable was found within Developer; the previously
located cache is outside the permitted boundary and was not accessed. Thus
Prettier checks are unavailable for the report JSON. No new formatting tooling
or dependencies were introduced. JSON validity and finite serialization were
checked using the standard library.

Limitations and next work
-------------------------
This is a reproducible preflight, not completion of the scientific research.
The absent patch cannot be reviewed. Data provenance, geography, overlap and
Onslow audits, checkpoint compatibility, actual simulation extension and every
convergence/sensitivity diagnostic still require real inputs and a compatible
scientific environment. Existing simulation/audit stages retain their previously
identified checkpoint-compatibility and output-protection limitations; preflight
does not certify them safe for continuation.

All new reports use new paths. Historical outputs and source datasets were not
changed. AGENTS.md remains local and ignored. After the initial audit, the user
explicitly requested Bina, the identity associated with httpsbina on GitHub.
The repository-local name was set to Bina; the existing email was preserved.
Author and committer now match the feature-branch history. The original audit
reports retain their historical snapshots from before that authorization.
