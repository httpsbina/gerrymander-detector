"""Audit a shared prefix, then continue every chain from its full history."""

import argparse
import copy
import fcntl
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".venv/matplotlib"))
from src.chain.run_texas_until_freeze import advance, audit_milestone
from src.chain.run_texas_matched import matched_round, finish


def prefix_manifest(manifests, steps):
    combined = {"source_code": manifests["tx_rebuild"]["source_code"], "experiments": {}}
    for key, value in manifests.items():
        experiment = copy.deepcopy(value["experiments"][key])
        if experiment["steps"] < steps:
            raise ValueError("Shared prefix exceeds a complete chain history")
        experiment["steps"] = steps
        combined["experiments"][key] = experiment
    combined["purpose"] = "Shared-prefix comparison only; full histories remain the continuation source."
    return combined


def first_joint_target(manifests, prefix):
    longest = max(value["experiments"][key]["steps"] for key, value in manifests.items())
    return max(prefix + 5000, ((longest + 4999) // 5000) * 5000)


def execute(manifests, destination, shared=45000):
    baseline = manifests["tx_rebuild"]["experiments"]["tx_rebuild"]
    if baseline["steps"] < shared:
        raise ValueError("Baseline has not completed the requested shared prefix")
    # Only the dispersed cohort advances during this initial catch-up.
    if manifests["tx_dispersed"]["experiments"]["tx_dispersed"]["steps"] < shared:
        directory = destination / "dispersed_catch_up"
        directory.mkdir()
        advance(manifests["tx_dispersed"], "tx_dispersed", shared, directory)
    comparison = destination / f"shared_prefix_{shared:06d}"
    comparison.mkdir()
    manifest = prefix_manifest(manifests, shared)
    (comparison / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    audit_milestone(manifest, comparison / "comparison")
    record = {"eligible_for_freeze": False, "shared_prefix_states": shared,
              "continuation_lengths": {key: value["experiments"][key]["steps"] for key, value in manifests.items()},
              "extra_states_preserved": True, "next_shared_audit": first_joint_target(manifests, shared)}
    (comparison / "continuation_record.json").write_text(json.dumps(record, indent=2) + "\n")
    target = record["next_shared_audit"]
    while True:
        directory = destination / f"shared_{target:06d}"
        directory.mkdir()
        matched_round(manifests, target, directory / "continuation")
        combined = {"source_code": manifest["source_code"], "experiments":
                    {key: copy.deepcopy(value["experiments"][key]) for key, value in manifests.items()}}
        if {e["steps"] for e in combined["experiments"].values()} != {target}:
            raise ValueError("Full-history joint audit requires equal complete lengths")
        (directory / "manifest.json").write_text(json.dumps(combined, indent=2) + "\n")
        if audit_milestone(combined, directory / "audit_all"):
            finish(directory / "audit_all/snapshot/manifest.json", directory / "audit_all/audit",
                   directory / "freeze_figures", target)
            return
        target += 5000


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-manifest", type=Path, required=True)
    parser.add_argument("--dispersed-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    for path in (args.baseline_manifest, args.dispersed_manifest, args.output_dir):
        path.resolve().relative_to(ROOT)
    with (ROOT / ".venv/texas-matched.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        values = [json.loads(path.read_text()) for path in (args.baseline_manifest, args.dispersed_manifest)]
        if values[0]["source_code"] != values[1]["source_code"]:
            raise ValueError("Cohort source profiles differ")
        manifests = {}
        for value, key in zip(values, ("tx_rebuild", "tx_dispersed")):
            if set(value["experiments"]) != {key} or len(value["experiments"][key]["seeds"]) != 4:
                raise ValueError("Exactly four chains per registered cohort required")
            manifests[key] = value
        args.output_dir = args.output_dir.resolve()
        args.output_dir.mkdir(parents=True, exist_ok=False)
        execute(manifests, args.output_dir)


if __name__ == "__main__":
    main()
