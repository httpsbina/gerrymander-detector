"""Verify transferred boundaries by exact replay before continuing chains."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
from importlib import metadata
import json
import os
from pathlib import Path
import pickle
import platform
import subprocess
import sys

from src.chain.benchmark_baselines import checkpoint_path
from src.chain.checkpoint_integrity import file_sha256

ROOT = Path(__file__).resolve().parents[2]


def replay(key, experiment, seed, destination):
    directory = ROOT / experiment["input_dir"]
    final_path = checkpoint_path(directory.parent / "checkpoints", experiment, seed, experiment["steps"])
    prior = checkpoint_path(directory.parent / "checkpoints", experiment, seed, experiment["steps"] - 100)
    with final_path.open("rb") as stream:
        expected = pickle.load(stream)
    runtime = expected["provenance"]["runtime"]
    actual = {"python": sys.version, "platform": platform.platform(),
              "packages": {name: metadata.version(name) for name in runtime["packages"]}}
    if actual != runtime:
        raise ValueError("Runtime differs from the checkpoint; exact continuation is not certified")
    destination.mkdir(parents=True, exist_ok=False)
    registry = json.loads((ROOT / experiment["seed_configs"][str(seed)]).read_text())
    plan = registry["states"][experiment["state"]]["plans"][experiment["starting_plan"]]
    plan["output_dir"] = str((destination / "ensembles").relative_to(ROOT))
    plan["checkpoint_dir"] = str((destination / "checkpoints").relative_to(ROOT))
    config = destination / "config.json"
    config.write_text(json.dumps(registry, indent=2) + "\n")
    command = [sys.executable, "main.py", "--nc" if experiment["state"] == "north_carolina" else "--texas",
               "--year", experiment["starting_plan"], "--config", str(config.relative_to(ROOT)),
               "--stage", "simulate", "--steps", "100", "--seed", str(seed), "--resume-from", str(prior.relative_to(ROOT))]
    env = dict(os.environ, PYTHONHASHSEED="0", OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1")
    with (destination / "replay.log").open("x") as stream:
        subprocess.run(command, cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT, check=True)
    tag = f"{experiment['epsilon']:g}".replace(".", "p")
    pattern = f"{experiment['prefix']}_chain_eps{tag}_seed{seed}_steps*.csv"
    original = []
    for path in sorted(directory.glob(pattern)):
        with path.open() as stream:
            original.extend(row for row in csv.DictReader(stream)
                            if experiment["steps"] - 100 <= int(row["step"]) < experiment["steps"])
    outputs = list((destination / "ensembles").glob(pattern))
    if len(outputs) != 1:
        raise ValueError("Replay did not produce one complete segment")
    with outputs[0].open() as stream:
        reproduced = list(csv.DictReader(stream))
    if len(original) != 100 or reproduced != original:
        raise ValueError("Replay CSV differs from the original trajectory")
    with checkpoint_path(destination / "checkpoints", experiment, seed, experiment["steps"]).open("rb") as stream:
        observed = pickle.load(stream)
    for field in ("assignment", "plan_hash", "random_state", "provenance", "next_step", "seed"):
        if observed[field] != expected[field]:
            raise ValueError(f"Replay checkpoint differs: {field}")
    return {"experiment": key, "seed": seed, "replayed_states": 100, "exact_match": True,
            "source_checkpoint_sha256": file_sha256(final_path), "command": command[1:]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--verification-dir", type=Path, default=Path("transfer_verification"))
    args = parser.parse_args()
    if args.workers < 1:
        raise ValueError("Positive replay worker count required")
    args.verification_dir.resolve().relative_to(ROOT)
    for name, expected in json.loads((ROOT / "SHA256SUMS.json").read_text()).items():
        path = (ROOT / name).resolve()
        path.relative_to(ROOT)
        if file_sha256(path) != expected:
            raise ValueError(f"Transfer checksum mismatch: {name}")
    manifest = json.loads((ROOT / "manifest.json").read_text())
    args.verification_dir.mkdir(parents=True, exist_ok=False)
    jobs = [(key, experiment, seed) for key, experiment in manifest["experiments"].items() for seed in experiment["seeds"]]
    def run(job):
        key, experiment, seed = job
        return replay(key, experiment, seed, (args.verification_dir / f"{key}_seed{seed}").resolve())
    with ThreadPoolExecutor(max_workers=min(args.workers, len(jobs))) as pool:
        records = list(pool.map(run, jobs))
    with (args.verification_dir / "replay_verification.json").open("x") as stream:
        json.dump(records, stream, indent=2)
        stream.write("\n")
    if args.verify_only:
        return
    texas = {key: e for key, e in manifest["experiments"].items() if e["state"] == "texas"}
    if set(texas) != {"tx_rebuild", "tx_dispersed"}:
        raise ValueError("Both Texas cohorts are required for production continuation")
    paths = []
    for key, e in texas.items():
        path = args.verification_dir / f"{key}_manifest.json"
        path.write_text(json.dumps({"source_code": manifest["source_code"], "experiments": {key: e}}, indent=2) + "\n")
        paths.append(path)
    subprocess.run([sys.executable, "src/chain/run_texas_matched.py", "--baseline-manifest", str(paths[0]),
                    "--dispersed-manifest", str(paths[1]), "--output-dir", "transferred_continuation"], cwd=ROOT, check=True)


if __name__ == "__main__":
    main()
