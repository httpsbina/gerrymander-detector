"""Pause a passing baseline while its dispersed cohort catches up."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import copy
import fcntl
import json
import math
import os
from pathlib import Path
import subprocess
import sys
from threading import Condition

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".venv/matplotlib"))
from src.analysis.audit_rebuild_campaign import METRICS
from src.chain.run_texas_until_freeze import advance, audit_milestone


def cohort_passes(directory, key, steps):
    report = json.loads((directory / f"milestone_{steps:06d}/audit/diagnostics.json").read_text())
    entry = report["experiments"][key]
    metrics = entry.get("diagnostics", {})
    if entry.get("integrity") != "pass" or set(metrics) != set(METRICS):
        return False
    for value in metrics.values():
        numbers = [value.get(name) for name in ("rank_split_rhat", "bulk_ess", "tail_ess")]
        if (any(v is None or not math.isfinite(v) for v in numbers)
                or not value["all_finite"] or value["screening_flags"]
                or numbers[0] >= 1.01 or min(numbers[1:]) < 400
                or value["ess_screening_minimum"] != 400):
            return False
    return True


def catch_up(manifests, destination):
    """Advance both cohorts without letting the dispersed cohort overtake."""
    condition = Condition()
    baseline = manifests["tx_rebuild"]["experiments"]["tx_rebuild"]
    dispersed = manifests["tx_dispersed"]["experiments"]["tx_dispersed"]
    if dispersed["steps"] > baseline["steps"]:
        raise ValueError("Dispersed cohort is longer; preserve and review both complete histories")
    state = {"frontier": baseline["steps"], "target": None, "failed": False}
    directories = {key: destination / key for key in manifests}
    for directory in directories.values():
        directory.mkdir(parents=True, exist_ok=False)

    def run(key):
        manifest = manifests[key]
        experiment = manifest["experiments"][key]
        directory = directories[key]
        try:
            if experiment["steps"] % 5000 == 0:
                audit_milestone(manifest, directory / f"milestone_{experiment['steps']:06d}")
            if key == "tx_rebuild":
                while experiment["steps"] % 5000 or not cohort_passes(directory, key, experiment["steps"]):
                    with condition:
                        if state["failed"]:
                            raise RuntimeError("Dispersed scheduling failed; completed segments preserved")
                    target = (experiment["steps"] // 5000 + 1) * 5000
                    advance(manifest, key, target, directory)
                    with condition:
                        state["frontier"] = experiment["steps"]
                        condition.notify_all()
                with condition:
                    state["target"] = experiment["steps"]
                    condition.notify_all()
                print(json.dumps({"baseline_paused_at": experiment["steps"]}), flush=True)
            else:
                while True:
                    with condition:
                        condition.wait_for(lambda: state["failed"] or state["target"] is not None
                                           or experiment["steps"] < state["frontier"])
                        if state["failed"]:
                            raise RuntimeError("Baseline scheduling failed; completed segments preserved")
                        limit = state["target"] if state["target"] is not None else state["frontier"]
                        if experiment["steps"] == limit:
                            return
                        target = min(limit, (experiment["steps"] // 5000 + 1) * 5000)
                    advance(manifest, key, target, directory)
        except BaseException:
            with condition:
                state["failed"] = True
                condition.notify_all()
            raise

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(run, manifests))
    return state["target"]


def matched_round(manifests, target, destination):
    def run(key):
        directory = destination / key
        directory.mkdir(parents=True, exist_ok=False)
        advance(manifests[key], key, target, directory)
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(run, manifests))


def finish(manifest_path, audit_directory, figures, target):
    from src.analysis.freeze_baseline import freeze, register_freeze, tag_freeze
    subprocess.run([sys.executable, "src/analysis/plot_rebuild_campaign.py", "--manifest",
                    str(manifest_path.relative_to(ROOT)), "--output-dir", str(figures.relative_to(ROOT))],
                   cwd=ROOT, check=True)
    destination = ROOT / "deliverables" / f"texas-baseline-freeze-{target}"
    freeze("texas", manifest_path, audit_directory, figures, destination)
    register_freeze("texas", destination)
    if (ROOT / ".git").exists():
        print(f"Freeze tag created: {tag_freeze('texas', destination, target)}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-manifest", type=Path, required=True)
    parser.add_argument("--dispersed-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    for path in (args.baseline_manifest, args.dispersed_manifest, args.output_dir):
        path.resolve().relative_to(ROOT)
    # A common lock prevents two matched controllers from writing the same chains.
    with (ROOT / ".venv/texas-matched.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        inputs = [json.loads(path.read_text()) for path in (args.baseline_manifest, args.dispersed_manifest)]
        if inputs[0]["source_code"] != inputs[1]["source_code"]:
            raise ValueError("Cohort source profiles differ")
        manifests = {}
        for value, key in zip(inputs, ("tx_rebuild", "tx_dispersed")):
            if set(value["experiments"]) != {key} or len(value["experiments"][key]["seeds"]) != 4:
                raise ValueError("Exactly four chains in each registered cohort required")
            manifests[key] = copy.deepcopy(value)
        args.output_dir = args.output_dir.resolve()
        args.output_dir.mkdir(parents=True, exist_ok=False)
        target = catch_up(manifests, args.output_dir / "catch_up")
        round_number = 0
        while True:
            round_number += 1
            directory = args.output_dir / f"joint_{target:06d}"
            directory.mkdir()
            combined = {"source_code": inputs[0]["source_code"], "experiments":
                        {key: value["experiments"][key] for key, value in manifests.items()}}
            if {e["steps"] for e in combined["experiments"].values()} != {target}:
                raise ValueError("Joint audit requires all complete histories at the same length")
            with (directory / "manifest.json").open("x") as stream:
                json.dump(combined, stream, indent=2)
                stream.write("\n")
            if audit_milestone(combined, directory / "audit_all"):
                finish(directory / "audit_all/snapshot/manifest.json", directory / "audit_all/audit",
                       directory / "freeze_figures", target)
                return
            target += 5000
            matched_round(manifests, target, args.output_dir / f"matched_{round_number:04d}")


if __name__ == "__main__":
    main()
