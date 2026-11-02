"""Launch separately identified new-source experiments through the state CLI.

Historical chains are never read, replaced, or combined with this campaign.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.chain.checkpoint_integrity import file_sha256


BASE = Path("outputs/analysis/rdh_rebuild_2026-11-02")


def prepare(destination):
    for short in ("nc", "tx"):
        probe = ROOT / BASE / f"{short}_continuation_probe_v3/continuation_report.json"
        with probe.open() as stream:
            if not json.load(stream)["exact_continuation_match"]:
                raise ValueError(f"{short} continuation check has not passed")
    destination.mkdir(parents=True, exist_ok=False)
    manifest = {"schema_version": 1, "research_ready": False,
                "purpose": "New-source baseline and sensitivity experiments; not historical continuation",
                "seed_design": "Distinct seeds within each geometry across NC starting maps; graph sensitivity reuses seed labels, is not pooled, and is not assumed independent of the baseline",
                "experiments": {}, "commands": [],
                "source_code": {name: file_sha256(ROOT / name) for name in (
                    "main.py", "src/chain/run_ensemble.py", "src/chain/checkpoint_integrity.py",
                    "src/chain/run_rebuild_campaign.py")}}
    definitions = [
        ("tx_rebuild", "texas", "current", BASE / "tx_candidate/tx_candidate.gpkg", [1117, 2227, 3331]),
        ("nc_block_union_2023", "north_carolina", "2023", BASE / "nc_block_union_candidate/nc_block_union_candidate.gpkg", [707, 808, 909]),
        ("nc_block_union_2025", "north_carolina", "2025", BASE / "nc_block_union_candidate/nc_block_union_candidate.gpkg", [1707, 1808, 1909]),
        ("nc_precinct_sensitivity_2023", "north_carolina", "2023", BASE / "nc_common_candidate/nc_common_candidate.gpkg", [707, 808, 909]),
        ("nc_precinct_sensitivity_2025", "north_carolina", "2025", BASE / "nc_common_candidate/nc_common_candidate.gpkg", [1707, 1808, 1909]),
    ]
    for key, state_key, year, dataset, seeds in definitions:
        with (ROOT / "configs/states.json").open() as stream:
            registry = json.load(stream)
        state = registry["states"][state_key]
        plan = state["plans"][year]
        label = key + "_20261102"
        experiment_root = destination / key
        plan["state_label"] = label
        plan["output_dir"] = str((experiment_root / "ensembles").relative_to(ROOT))
        plan["checkpoint_dir"] = str((experiment_root / "checkpoints").relative_to(ROOT))
        plan["audit"]["prefix"] = label
        plan["audit"]["seeds"] = seeds
        plan["audit"]["output_dir"] = str((experiment_root / "audit").relative_to(ROOT))
        state["dataset"] = str(dataset)
        state["status"] = "new_source_candidate_not_research_ready"
        state["plans"] = {year: plan}
        state["default_year"] = year
        registry["states"] = {state_key: state}
        config = destination / f"{key}.json"
        with config.open("x") as stream:
            json.dump(registry, stream, indent=2, allow_nan=False)
            stream.write("\n")
        steps = plan["audit"]["steps"]
        manifest["experiments"][key] = {
            "state": state_key, "starting_plan": year, "dataset": str(dataset),
            "dataset_sha256": file_sha256(ROOT / dataset), "districts": state["districts"],
            "epsilon": plan["epsilon"], "node_repeats": plan["node_repeats"],
            "seeds": seeds, "steps": steps, "warmup": plan["audit"]["warmup"],
            "window": plan["audit"]["window"], "prefix": label,
            "input_dir": plan["output_dir"], "config": str(config.relative_to(ROOT)),
        }
        for seed in seeds:
            command = [sys.executable, str(ROOT / "main.py"),
                       "--texas" if state_key == "texas" else "--nc",
                       "--year", year, "--config", str(config),
                       "--stage", "simulate", "--steps", str(steps), "--seed", str(seed)]
            manifest["commands"].append({"experiment": key, "seed": seed, "command": command,
                                         "log": str(destination / f"{key}_seed{seed}.log")})
    with (destination / "manifest.json").open("x") as stream:
        json.dump(manifest, stream, indent=2, allow_nan=False)
        stream.write("\n")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--run", action="store_true", help="Execute the full configured lengths")
    args = parser.parse_args()
    destination = args.output_dir.resolve()
    destination.relative_to(ROOT)
    if args.workers < 1:
        raise ValueError("Workers must be positive")
    manifest = prepare(destination)
    print(f"Prepared {len(manifest['commands'])} chain commands, with paired NC graph-sensitivity seeds: {destination}", flush=True)
    if not args.run:
        return 0
    env = dict(os.environ, PYTHONHASHSEED="0", PYTHONUNBUFFERED="1",
               MPLCONFIGDIR=str(ROOT / "data/external/rdh/rebuild_2026-11-02/runtime/matplotlib312"))
    def run(item):
        experiment = manifest["experiments"][item["experiment"]]
        if file_sha256(ROOT / experiment["dataset"]) != experiment["dataset_sha256"]:
            raise ValueError("Dataset changed after campaign preparation")
        for name, expected in manifest["source_code"].items():
            if file_sha256(ROOT / name) != expected:
                raise ValueError("Campaign code changed during execution")
        started = time.monotonic()
        with Path(item["log"]).open("x") as log:
            result = subprocess.run(item["command"], cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
        return {"experiment": item["experiment"], "seed": item["seed"],
                "exit_code": result.returncode, "seconds": time.monotonic() - started}
    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(run, item) for item in manifest["commands"]]
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            print(json.dumps(result), flush=True)
    with (destination / "completion.json").open("x") as stream:
        json.dump({"research_ready": False, "results": results}, stream, indent=2)
    return 1 if any(row["exit_code"] for row in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
