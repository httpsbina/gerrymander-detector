"""Measure exact baseline continuations without overwriting the original campaign."""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import copy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.chain.checkpoint_integrity import file_sha256

KEYS = ("nc_block_union_2023", "nc_block_union_2025", "tx_rebuild")


def checkpoint_path(directory, experiment, seed, next_step):
    tag = f"{experiment['epsilon']:g}".replace(".", "p")
    return directory / f"{experiment['prefix']}_checkpoint_eps{tag}_seed{seed}_next{next_step}.pkl"


def prepare(source, registry_path, destination):
    source = json.loads(source.read_text())
    registry = json.loads(registry_path.read_text())
    for name in ("src/chain/run_ensemble.py", "src/chain/checkpoint_integrity.py"):
        if file_sha256(ROOT / name) != source["source_code"][name]:
            raise ValueError("Sampler or checkpoint implementation differs from the baseline")
    destination.mkdir(parents=True, exist_ok=False)
    manifest = {"schema_version": 1, "purpose": "Exact continuation of existing baseline chains",
                "created_utc": datetime.now(timezone.utc).isoformat(), "experiments": {},
                "source_code": {name: file_sha256(ROOT / name) for name in (
                    "main.py", "src/chain/run_ensemble.py", "src/chain/checkpoint_integrity.py")}}
    references = []
    for key in KEYS:
        experiment = copy.deepcopy(source["experiments"][key])
        if file_sha256(ROOT / experiment["dataset"]) != experiment["dataset_sha256"]:
            raise ValueError("Baseline dataset fingerprint differs")
        original = (ROOT / experiment["input_dir"]).resolve()
        original.relative_to(ROOT)
        folder = destination / key
        ensembles, checkpoints = folder / "ensembles", folder / "checkpoints"
        ensembles.mkdir(parents=True);checkpoints.mkdir()
        for path in original.glob("*.csv"):
            (ensembles / path.name).symlink_to(os.path.relpath(path, ensembles))
            references.append({"path": str(path.relative_to(ROOT)), "sha256": file_sha256(path)})
        for seed in experiment["seeds"]:
            path = checkpoint_path(original.parent / "checkpoints", experiment, seed, experiment["steps"])
            (checkpoints / path.name).symlink_to(os.path.relpath(path, checkpoints))
            references.append({"path": str(path.relative_to(ROOT)), "sha256": file_sha256(path)})
        experiment["input_dir"] = str(ensembles.relative_to(ROOT))
        experiment["config"] = str((destination / "states.json").relative_to(ROOT))
        manifest["experiments"][key] = experiment
        state = registry["states"][experiment["state"]]
        plan = state["plans"][experiment["starting_plan"]]
        plan["output_dir"] = experiment["input_dir"]
        plan["checkpoint_dir"] = str(checkpoints.relative_to(ROOT))
    manifest["original_inputs"] = references
    with (destination / "manifest_initial.json").open("x") as stream:
        json.dump(manifest, stream, indent=2);stream.write("\n")
    with (destination / "states.json").open("x") as stream:
        json.dump(registry, stream, indent=2);stream.write("\n")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    for path in (args.source_manifest, args.registry, args.output_dir):
        path.resolve().relative_to(ROOT)
    destination = args.output_dir.resolve()
    manifest = prepare(args.source_manifest, args.registry, destination)
    steps = {(key, seed): experiment["steps"] for key, experiment in manifest["experiments"].items() for seed in experiment["seeds"]}
    nc = [(key, seed) for key in KEYS[:2] for seed in manifest["experiments"][key]["seeds"]]
    tx = [("tx_rebuild", seed) for seed in manifest["experiments"]["tx_rebuild"]["seeds"]]
    phases = [("nc_serial", nc[:1], 500, 1), ("nc_five_parallel", nc[1:], 500, 5),
              ("nc_six_parallel", nc, 500, 6), ("tx_four_parallel", tx, 200, 4)]
    env = dict(os.environ, PYTHONHASHSEED="0", PYTHONUNBUFFERED="1", OMP_NUM_THREADS="1",
               OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1",
               MPLCONFIGDIR=str(ROOT / ".venv/matplotlib"))
    results = []
    for label, jobs, count, workers in phases:
        started = time.monotonic()
        def run(job):
            key, seed = job
            e = manifest["experiments"][key]
            checkpoint = checkpoint_path((ROOT / e["input_dir"]).parent / "checkpoints", e, seed, steps[job])
            command = [sys.executable, str(ROOT / "main.py"), "--nc" if e["state"] == "north_carolina" else "--texas",
                       "--year", e["starting_plan"], "--config", str(destination / "states.json"),
                       "--stage", "simulate", "--steps", str(count), "--seed", str(seed), "--resume-from", str(checkpoint)]
            begin = time.monotonic()
            with (destination / f"{label}_seed{seed}.log").open("x") as log:
                result = subprocess.run(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
            if result.returncode:
                raise RuntimeError(f"Continuation failed: {label}/{seed}, exit {result.returncode}")
            return {"experiment": key, "seed": seed, "first_step": steps[job], "new_states": count,
                    "seconds": time.monotonic() - begin, "command": [p.replace(str(ROOT) + "/", "") for p in command]}
        with ThreadPoolExecutor(max_workers=workers) as pool:
            completed = [future.result() for future in as_completed([pool.submit(run, job) for job in jobs])]
        seconds = time.monotonic() - started
        entry = {"phase": label, "workers": workers, "seconds": seconds, "states": count * len(jobs),
                 "aggregate_steps_per_hour": 3600 * count * len(jobs) / seconds, "jobs": completed}
        results.append(entry)
        for job in jobs:steps[job] += count
        with (destination / f"{label}_timing.json").open("x") as stream:json.dump(entry, stream, indent=2);stream.write("\n")
        print(json.dumps({k:v for k,v in entry.items() if k != "jobs"}), flush=True)
    for key, e in manifest["experiments"].items():
        lengths = {steps[(key, seed)] for seed in e["seeds"]}
        if len(lengths) != 1:raise ValueError("Unequal chain lengths after benchmark")
        e["steps"] = lengths.pop()
    with (destination / "manifest_benchmark.json").open("x") as stream:json.dump(manifest, stream, indent=2);stream.write("\n")
    with (destination / "throughput.json").open("x") as stream:json.dump({"phases":results,"timing_scope":"End-to-end wall time including interpreter startup, graph construction and checkpoint I/O"},stream,indent=2);stream.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
