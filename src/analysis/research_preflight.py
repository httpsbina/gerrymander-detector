"""Read-only input and segment audit without scientific Python dependencies."""

import csv
import hashlib
from importlib import metadata
import json
import math
from pathlib import Path
import platform
import re
import subprocess
import sys


DEPENDENCIES = (
    "geopandas", "gerrychain", "networkx", "numpy", "pandas", "arviz",
    "shapely", "pyproj",
)
DIAGNOSTICS = (
    "rank_normalized_split_rhat", "bulk_ess", "tail_ess", "mcse",
    "trace_stability", "window_stability", "warmup_sensitivity",
    "starting_map_sensitivity", "election_model_sensitivity",
    "constraint_sensitivity", "checkpoint_continuation_reproducibility",
    "block_coverage", "unique_geographic_ids", "population_election_totals",
    "geometry_validity_and_overlaps", "adjacency_and_district_contiguity",
)


def local_path(root, value):
    """Limit configured inputs to the checkout, including symlink targets."""
    path = (root / value).resolve()
    path.relative_to(root.resolve())
    return path


def receipt(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return {"path": str(path), "bytes": path.stat().st_size,
            "sha256": digest.hexdigest()}


def audit_segments(paths, seed, epsilon, districts):
    """Validate every supplied row; never truncate to a configured target length."""
    issues, files, steps = [], [], set()
    required = {
        "step", "seed", "epsilon", "dem_seats", "efficiency_gap",
        "cut_edges", "max_abs_pop_dev", "plan_hash",
    }
    for path in paths:
        entry = receipt(path)
        files.append(entry)
        match = re.search(r"steps(\d+)-(\d+)\.csv$", path.name)
        if not match:
            issues.append(f"Unexpected segment filename: {path.name}")
            continue
        first, last = map(int, match.groups())
        count = 0
        try:
            with path.open(encoding="utf-8-sig", newline="") as stream:
                reader = csv.DictReader(stream)
                if not required.issubset(reader.fieldnames or []):
                    raise ValueError("missing required columns")
                for row in reader:
                    expected_step = first + count
                    count += 1
                    step = int(row["step"])
                    if step != expected_step or step > last:
                        raise ValueError(f"noncontiguous row at step {step}")
                    if step in steps:
                        raise ValueError(f"overlapping step {step}")
                    steps.add(step)
                    if int(row["seed"]) != seed:
                        raise ValueError("seed mismatch")
                    numeric = {key: float(row[key]) for key in (
                        "epsilon", "dem_seats", "efficiency_gap", "cut_edges",
                        "max_abs_pop_dev",
                    )}
                    if not all(math.isfinite(value) for value in numeric.values()):
                        raise ValueError("nonfinite numeric value")
                    if not (numeric["dem_seats"].is_integer()
                            and 0 <= numeric["dem_seats"] <= districts):
                        raise ValueError("invalid seat count")
                    if not (numeric["cut_edges"].is_integer() and numeric["cut_edges"] >= 0):
                        raise ValueError("invalid cut edge count")
                    if not math.isclose(numeric["epsilon"], epsilon, rel_tol=0, abs_tol=1e-10):
                        raise ValueError("epsilon mismatch")
                    if not 0 <= numeric["max_abs_pop_dev"] <= epsilon + 1e-10:
                        raise ValueError("population tolerance violation")
                    if not re.fullmatch(r"[a-f0-9]{64}", row["plan_hash"]):
                        raise ValueError("invalid plan hash")
            if count != last - first + 1:
                raise ValueError("filename range does not match row count")
        except (ValueError, KeyError, TypeError, csv.Error) as exc:
            issues.append(f"{path.name}: {exc}")
        entry["rows_read"] = count
    if steps and (min(steps) != 0 or len(steps) != max(steps) + 1):
        issues.append("Missing steps: segments do not cover step zero through the final step")
    if not paths:
        issues.append("No chain segments found")
    return {
        "seed": seed, "status": "fail" if issues else "pass",
        "files": files, "issues": issues,
        "observed_unique_steps": len(steps),
        "first_step": min(steps) if steps else None,
        "last_step": max(steps) if steps else None,
        "length_verified": bool(paths) and not issues,
    }


def git_value(root, *args):
    result = subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True, check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def build_report(root, state_key, year, state, plan, command):
    root = Path(root).resolve()
    versions = {}
    for name in DEPENDENCIES:
        try:
            versions[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            versions[name] = None
    dataset = local_path(root, state["dataset"])
    ensemble = local_path(root, plan["output_dir"])
    checkpoints = local_path(root, plan["checkpoint_dir"])
    audit = plan["audit"]
    tag = f"{plan['epsilon']:g}".replace(".", "p")
    candidates = sorted(ensemble.glob(
        f"{audit['prefix']}_chain_eps{tag}_seed*_steps*.csv"
    ))
    discovered_seeds = set()
    for path in candidates:
        match = re.fullmatch(
            re.escape(f"{audit['prefix']}_chain_eps{tag}_seed")
            + r"(-?\d+)_steps.*\.csv", path.name,
        )
        if match:
            discovered_seeds.add(int(match.group(1)))
    chains = []
    for seed in sorted(set(audit["seeds"]) | discovered_seeds):
        paths = sorted(ensemble.glob(
            f"{audit['prefix']}_chain_eps{tag}_seed{seed}_steps*.csv"
        ))
        paths = [local_path(root, str(path)) for path in paths]
        chain = audit_segments(paths, seed, plan["epsilon"], state["districts"])
        chain["configured_seed"] = seed in audit["seeds"]
        chains.append(chain)
    checkpoint_files = [receipt(local_path(root, str(path))) for path in sorted(
        checkpoints.glob(f"{audit['prefix']}_checkpoint_*.pkl")
    )]
    diagnostics = {name: "unavailable" for name in DIAGNOSTICS}
    if state_key == "north_carolina":
        diagnostics.update({"onslow_split_and_both_assignments": "unavailable",
                            "separate_and_joint_initialization_groups": "unavailable"})
    return {
        "schema_version": 1, "execution_status": "completed",
        "research_ready": False,
        "scope": "Input inventory and CSV integrity only; no scientific certification",
        "state": state_key, "starting_plan": year, "command": command,
        "configuration": {"state": state, "plan": plan},
        "provenance": {
            "commit": git_value(root, "rev-parse", "HEAD"),
            "branch": git_value(root, "branch", "--show-current"),
            "working_tree": git_value(root, "status", "--porcelain"),
            "registry": receipt(root / "configs/states.json"),
            "audit_source": receipt(root / "src/analysis/research_preflight.py"),
            "cli_source": receipt(root / "main.py"),
            "sampler_source": receipt(root / "src/chain/run_ensemble.py"),
        },
        "environment": {"python": sys.version, "platform": platform.platform(),
                        "executable": sys.executable, "packages": versions},
        "dataset": receipt(dataset) if dataset.is_file() else {
            "path": str(dataset), "status": "missing",
        },
        "chains": chains, "checkpoints": checkpoint_files,
        "checkpoint_compatibility": "unavailable; pickle files are never loaded",
        "diagnostics": diagnostics,
        "interpretation": [
            "Configured lengths and totals are expectations, not measured results.",
            "Missing or nonfinite diagnostics mean not research-ready.",
            "ReCom is not established as uniform or fully legally constrained.",
            "Block vote allocations are modeled, not observed block returns.",
            "Texas PLANC2333 requires a separate block-resolution benchmark.",
            "No frequencies, probabilities, or calibrated p-values are estimated.",
        ],
    }


def write_report(report, directory):
    """Create a fresh output directory; refuse even an empty existing directory."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    with (directory / "report.json").open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write("\n")
    lines = [
        f"{report['state']} / {report['starting_plan']}",
        "Execution: completed", "Research-ready: NO",
        f"Dataset: {report['dataset']['path']}",
    ]
    for chain in report["chains"]:
        lines.append(f"Seed {chain['seed']}: {chain['status']}; "
                     f"verified length: {chain['length_verified']}; "
                     f"observed steps: {chain['observed_unique_steps']}")
        lines.extend(f"  {issue}" for issue in chain["issues"])
    lines.append("Required scientific diagnostics: unavailable (see report.json)")
    lines.extend(report["interpretation"])
    with (directory / "report.txt").open("x", encoding="utf-8") as stream:
        stream.write("\n".join(lines) + "\n")
