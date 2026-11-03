"""Record immutable numerical freezes and their reproducible result tables."""

import argparse
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.analysis.audit_rebuild_campaign import METRICS
from src.chain.checkpoint_integrity import file_sha256
from src.chain.benchmark_baselines import checkpoint_path


def require_screens(report, state):
    if state == "nc":
        keys = ["nc_block_union_2023", "nc_block_union_2025"]
        groups = {key: report["experiments"][key] for key in keys}
        groups["joint"] = report["joint_nc"]["nc_block_union"]
    else:
        groups = {key: report["experiments"][key] for key in ("tx_rebuild", "tx_dispersed")}
        groups["joint"] = report["joint_texas"]
    thresholds = {key: (600 if state == "nc" else 800) if key == "joint" else 400 for key in groups}
    for key, entry in groups.items():
        if entry.get("integrity", entry.get("status")) not in ("pass", "computed"):
            raise ValueError(f"Incomplete integrity audit: {key}")
        if set(entry.get("diagnostics", {})) != set(METRICS):
            raise ValueError(f"Missing primary metric: {key}")
        for metric, values in entry["diagnostics"].items():
            numbers = [values.get(name) for name in ("rank_split_rhat", "bulk_ess", "tail_ess",
                       "mcse_mean", "mcse_sd", "mcse_q05", "mcse_q95")]
            if any(value is None for value in numbers) or not np.isfinite(numbers).all():
                raise ValueError(f"Nonfinite primary diagnostic: {key}/{metric}")
            if (not values["all_finite"] or values["screening_flags"]
                    or values["rank_split_rhat"] >= 1.01
                    or min(values["bulk_ess"], values["tail_ess"]) < thresholds[key]
                    or values["ess_screening_minimum"] != thresholds[key]):
                raise ValueError(f"Primary screen failed: {key}/{metric}")
        if not entry.get("warmup_sensitivity"):
            raise ValueError(f"Missing warmup checks: {key}")
        for burn, metrics in entry["warmup_sensitivity"].items():
            if set(metrics) != set(METRICS) or any(not v["all_finite"] for v in metrics.values()):
                raise ValueError(f"Unavailable warmup diagnostic: {key}/{burn}")
    return groups


def result_tables(report, state, audit_dir):
    groups = require_screens(report, state)
    tables = {}
    for name in ("chain_summary", "windows"):
        frame = pd.read_csv(audit_dir / f"{name}.csv")
        if not len(frame) or frame.isna().any().any():
            raise ValueError(f"Missing or nonfinite {name} entries")
        if not np.isfinite(frame.select_dtypes(include="number").to_numpy()).all():
            raise ValueError(f"Nonfinite {name} entries")
        tables[name] = frame.to_dict("records")
    return {"state": state, "primary_diagnostics": {key: e["diagnostics"] for key, e in groups.items()},
            "warmup_sensitivity": {key: e["warmup_sensitivity"] for key, e in groups.items()}, **tables}


def freeze(state, manifest_path, audit_dir, figures_dir, destination):
    manifest_path, audit_dir, figures_dir, destination = [
        path.resolve() for path in (manifest_path, audit_dir, figures_dir, destination)]
    manifest = json.loads(manifest_path.read_text())
    report = json.loads((audit_dir / "diagnostics.json").read_text())
    if report["manifest_sha256"] != file_sha256(manifest_path):
        raise ValueError("Audit and freeze manifest differ")
    results = result_tables(report, state, audit_dir)
    figures = sorted(figures_dir.glob("*.png"))
    expected = 6 if state == "nc" else 4
    if len(figures) != expected or not (figures_dir / "figure_manifest.json").is_file():
        raise ValueError("Complete trace/rank plots are required")
    files = {manifest_path, Path("docs/freeze_rule.md"), Path("requirements-research-macos-arm64-py312.txt")}
    files.update(Path(name) for name in ("reproduce_paper.py", "src/analysis/freeze_baseline.py",
                 "src/analysis/audit_rebuild_campaign.py", "src/analysis/audit_ensemble_chains.py",
                 "src/analysis/plot_rebuild_campaign.py", "src/analysis/texas_cohort_integrity.py",
                 "src/data_prep/prepare_dispersed_texas_starts.py"))
    files.update(audit_dir.glob("*"))
    files.update(figures_dir.glob("*"))
    files.update(Path(name) for name in manifest["source_code"])
    for e in manifest["experiments"].values():
        files.add(Path(e["dataset"]))
        files.add(Path(e["config"]))
        files.update(Path(p) for p in e.get("seed_configs", {}).values())
        files.update(Path(e["input_dir"]).glob("*.csv"))
        for seed in e["seeds"]:
            files.add(checkpoint_path(Path(e["input_dir"]).parent / "checkpoints", e, seed, e["steps"]))
    receipts = {}
    for path in files:
        absolute = ROOT / path
        absolute.resolve().relative_to(ROOT)
        if not absolute.is_file():
            raise FileNotFoundError(absolute)
        receipts[str(absolute.relative_to(ROOT))] = file_sha256(absolute)
    destination.mkdir(parents=True, exist_ok=False)
    with (destination / "results.json").open("x") as stream:
        json.dump(results, stream, indent=2, allow_nan=False)
        stream.write("\n")
    receipts[str((destination / "results.json").relative_to(ROOT))] = file_sha256(destination / "results.json")
    record = {"state": state, "status": "primary_convergence_frozen", "manifest": str(manifest_path.relative_to(ROOT)),
              "audit_dir": str(audit_dir.relative_to(ROOT)), "figures_dir": str(figures_dir.relative_to(ROOT)),
              "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "steps_per_chain": {key: e["steps"] for key, e in manifest["experiments"].items()},
              "checksums": dict(sorted(receipts.items())),
              "limitations": report["unresolved"]}
    with (destination / "freeze_manifest.json").open("x") as stream:
        json.dump(record, stream, indent=2, allow_nan=False)
        stream.write("\n")
    return record


def register_freeze(state, destination):
    """Register a verified freeze; publishing and tagging remain explicit steps."""
    destination = destination.resolve()
    record = json.loads((destination / "freeze_manifest.json").read_text())
    if record["status"] != "primary_convergence_frozen" or record["state"] != state:
        raise ValueError("Invalid freeze registration")
    registry_path = ROOT / "configs/paper_freezes.json"
    registry = json.loads(registry_path.read_text()) if registry_path.exists() else {}
    if state in registry:
        raise FileExistsError("State already has a registered freeze")
    registry[state] = str((destination / "freeze_manifest.json").relative_to(ROOT))
    results_path = ROOT / "results.json"
    results = json.loads(results_path.read_text()) if results_path.exists() else {}
    if state in results:
        raise FileExistsError("State already has frozen results")
    results[state] = json.loads((destination / "results.json").read_text())
    registry_path.write_text(json.dumps(registry, indent=2, allow_nan=False) + "\n")
    results_path.write_text(json.dumps(results, indent=2, allow_nan=False) + "\n")


def tag_freeze(state, destination, steps):
    """Commit only freeze records after checking the established identity."""
    def git(*args):
        return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()
    established = git("log", "-1", "--no-merges", "--format=%an <%ae>")
    if not established.startswith("Bina <"):
        raise ValueError("Established Bina identity unavailable; freeze records remain uncommitted")
    for variable in ("GIT_AUTHOR_IDENT", "GIT_COMMITTER_IDENT"):
        if git("var", variable).split(">", 1)[0] + ">" != established:
            raise ValueError("Git identity differs; refusing freeze commit")
    branch = git("branch", "--show-current")
    if not branch.startswith("research/"):
        raise ValueError("Freeze commits require a research branch")
    tag = f"{state}-baseline-{steps}"
    exists = subprocess.run(["git", "show-ref", "--verify", "--quiet", f"refs/tags/{tag}"], cwd=ROOT)
    if exists.returncode == 0:
        raise FileExistsError("Freeze tag already exists")
    paths = [str(destination.resolve().relative_to(ROOT)), "configs/paper_freezes.json", "results.json"]
    subprocess.run(["git", "add", "--", *paths], cwd=ROOT, check=True)
    subprocess.run(["git", "diff", "--cached", "--check"], cwd=ROOT, check=True)
    subprocess.run(["git", "commit", "--only", "-m", f"Freeze {state} baseline at {steps} states per chain", "--", *paths], cwd=ROOT, check=True)
    if git("show", "-s", "--format=%an <%ae>|%cn <%ce>") != established + "|" + established:
        raise ValueError("Recorded freeze commit identity differs; history was preserved")
    message = f"Freeze {state} baseline: {steps} states per chain; manifest SHA256 {file_sha256(destination / 'freeze_manifest.json')}"
    subprocess.run(["git", "tag", "-a", tag, "-m", message], cwd=ROOT, check=True)
    return tag


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", choices=("nc", "texas"), required=True)
    for name in ("manifest", "audit-dir", "figures-dir", "output-dir"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    for path in (args.manifest, args.audit_dir, args.figures_dir, args.output_dir):
        path.resolve().relative_to(ROOT)
    record = freeze(args.state, args.manifest, args.audit_dir, args.figures_dir, args.output_dir)
    print(json.dumps({key: record[key] for key in ("state", "status", "steps_per_chain")}))


if __name__ == "__main__":
    main()
