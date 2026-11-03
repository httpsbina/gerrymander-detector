"""Continue both Texas cohorts at fixed 5,000-state audit milestones."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import copy
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".venv/matplotlib"))
from src.chain.continue_baselines import run_wave
from src.chain.convergence_state import snapshot_manifest


def passing(entry):
    values = entry.get("diagnostics", {})
    return bool(values) and all(v["all_finite"] and not v["screening_flags"] for v in values.values())


def audit_milestone(manifest, destination):
    snapshot = snapshot_manifest(manifest, destination / "snapshot")
    command = [sys.executable, "src/analysis/audit_rebuild_campaign.py", "--manifest",
               str(snapshot.relative_to(ROOT)), "--output-dir", str((destination / "audit").relative_to(ROOT))]
    with (destination / "audit.log").open("x") as stream:
        subprocess.run(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, check=True)
    report = json.loads((destination / "audit/diagnostics.json").read_text())
    if any(e["integrity"] != "pass" for e in report["experiments"].values()):
        raise RuntimeError("Texas chain integrity failed; inspect the preserved milestone")
    entries = dict(report["experiments"])
    if "joint_texas" in report:
        entries["joint_texas"] = report["joint_texas"]
    if any(not v["all_finite"] for e in entries.values() for v in e["diagnostics"].values()):
        raise RuntimeError("Nonfinite primary diagnostic")
    status = {key: {name: {field: value[field] for field in
              ("rank_split_rhat", "bulk_ess", "tail_ess", "ess_screening_minimum")}
              for name, value in entry["diagnostics"].items()} for key, entry in entries.items()}
    with (destination / "progress.json").open("x") as stream:
        json.dump(status, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"milestone": str(destination.relative_to(ROOT)), "metrics": status}), flush=True)
    return "joint_texas" in entries and all(passing(e) for e in entries.values())


def advance(manifest, key, target, destination):
    e = manifest["experiments"][key]
    lengths = {(key, seed): e["steps"] for seed in e["seeds"]}
    while e["steps"] < target:
        count = min(1000, target - e["steps"])
        run_wave(manifest, [(key, seed, count) for seed in e["seeds"]], lengths,
                 destination / f"segments_{e['steps']:06d}", len(e["seeds"]))
        e["steps"] += count
        with (destination / f"manifest_{e['steps']:06d}.json").open("x") as stream:
            json.dump(manifest, stream, indent=2)
            stream.write("\n")
        if e["steps"] % 5000 == 0:
            audit_milestone(manifest, destination / f"milestone_{e['steps']:06d}")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-manifest", type=Path, required=True)
    parser.add_argument("--dispersed-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--first-joint-milestone", type=int, default=50000)
    args = parser.parse_args()
    for path in (args.baseline_manifest, args.dispersed_manifest, args.output_dir):
        path.resolve().relative_to(ROOT)
    baseline, dispersed = [json.loads(path.read_text()) for path in
                            (args.baseline_manifest, args.dispersed_manifest)]
    if baseline["source_code"] != dispersed["source_code"]:
        raise ValueError("Cohort source profiles differ")
    definitions = {**baseline["experiments"], **dispersed["experiments"]}
    if set(definitions) != {"tx_rebuild", "tx_dispersed"}:
        raise ValueError("Both and only the two registered Texas cohorts are required")
    target = args.first_joint_milestone
    if target % 5000 or target <= max(e["steps"] for e in definitions.values()):
        raise ValueError("First joint milestone must be a future multiple of 5000")
    args.output_dir.mkdir(parents=True, exist_ok=False)
    round_number = 0
    while True:
        round_number += 1
        round_dir = args.output_dir / f"round_{round_number:04d}"
        round_dir.mkdir()
        def cohort(key):
            directory = round_dir / key
            directory.mkdir()
            manifest = {"source_code": baseline["source_code"], "experiments": {key: copy.deepcopy(definitions[key])}}
            while manifest["experiments"][key]["steps"] < target:
                current = manifest["experiments"][key]["steps"]
                advance(manifest, key, min(target, (current // 5000 + 1) * 5000), directory)
            return manifest
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(cohort, definitions))
        definitions = {key: value for result in results for key, value in result["experiments"].items()}
        combined = {"source_code": baseline["source_code"], "experiments": definitions}
        with (round_dir / "manifest.json").open("x") as stream:
            json.dump(combined, stream, indent=2)
            stream.write("\n")
        if audit_milestone(combined, round_dir / "joint"):
            from src.analysis.freeze_baseline import freeze, register_freeze, tag_freeze
            figures = round_dir / "freeze_figures"
            subprocess.run([sys.executable, "src/analysis/plot_rebuild_campaign.py", "--manifest",
                            str((round_dir / "joint/snapshot/manifest.json").relative_to(ROOT)),
                            "--output-dir", str(figures.relative_to(ROOT))], cwd=ROOT, check=True)
            destination = ROOT / "deliverables" / f"texas-baseline-freeze-{target}"
            freeze("texas", round_dir / "joint/snapshot/manifest.json", round_dir / "joint/audit", figures, destination)
            register_freeze("texas", destination)
            if (ROOT / ".git").exists():
                tag = tag_freeze("texas", destination, target)
                print(f"Freeze tag created: {tag}", flush=True)
            print(f"Texas numerical freeze recorded at {target}; checksums and reproduction registry written", flush=True)
            return
        target += 5000


if __name__ == "__main__":
    main()
