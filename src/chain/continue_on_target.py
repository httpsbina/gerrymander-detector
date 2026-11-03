"""Try exact replay, then record authorized native-platform continuations."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from importlib import metadata
import json
import os
from pathlib import Path
import pickle
import platform
import subprocess
import sys

import numpy as np
import pandas as pd

from src.chain.benchmark_baselines import checkpoint_path
from src.chain.checkpoint_integrity import file_sha256
from src.chain.platform_transition import eligible_profile, prepare
from src.chain.resume_transfer import replay

ROOT = Path(__file__).resolve().parents[2]


def current_runtime(recorded):
    return {"python": sys.version, "platform": platform.platform(),
            "packages": {name: metadata.version(name) for name in recorded["packages"]}}


def complete_native_probe(destination, experiment, seed):
    outputs = list((destination / "ensembles").glob("*.csv"))
    if len(outputs) != 1:
        return False
    frame = pd.read_csv(outputs[0])
    columns = ["dem_seats", "efficiency_gap", "cut_edges", "mean_median", "max_abs_pop_dev"]
    return (len(frame) == 100 and frame.step.tolist() == list(range(experiment["steps"] - 100, experiment["steps"]))
            and np.isfinite(frame[columns].to_numpy()).all()
            and (frame.seed == seed).all()
            and np.allclose(frame.epsilon, experiment["epsilon"], rtol=0, atol=1e-10)
            and (frame.max_abs_pop_dev <= experiment["epsilon"] + 1e-10).all())


def verify_cohort(key, experiment, destination, workers, graph_cache, exact_only=False):
    destination.mkdir(parents=True, exist_ok=False)
    different = False
    for seed in experiment["seeds"]:
        path = checkpoint_path((ROOT / experiment["input_dir"]).parent / "checkpoints", experiment, seed, experiment["steps"])
        with path.open("rb") as stream:
            checkpoint = pickle.load(stream)
        source = checkpoint["provenance"]
        target = dict(source, runtime=current_runtime(source["runtime"]))
        different |= eligible_profile(source, target)
    if different and exact_only:
        raise ValueError("Exact-only mode rejects a runtime profile change")
    if different:
        converted, receipt = prepare(experiment, destination / "native_boundary", graph_cache)
    else:
        converted, receipt = experiment, {"files": {}, "chains": []}
    def run(seed):
        directory = destination / f"seed{seed}_replay"
        try:
            result = replay(key, converted, seed, directory)
            result["continuation_class"] = "cross_platform_exact_replay" if different else "exact_runtime_and_replay"
            result["bitwise_reproducibility_ends_at_transfer"] = False
            return result
        except ValueError as exc:
            eligible_failure = str(exc).startswith(("Replay CSV differs", "Replay checkpoint differs: assignment",
                                "Replay checkpoint differs: random_state", "Replay checkpoint differs: plan_hash"))
            if not different or not eligible_failure or not complete_native_probe(directory, converted, seed):
                raise
            return {"experiment": key, "seed": seed, "exact_match": False,
                    "continuation_class": "checkpoint_state_continuation",
                    "bitwise_reproducibility_ends_at_transfer": True,
                    "last_bitwise_source_step": experiment["steps"] - 1,
                    "new_segment_first_step": experiment["steps"], "replay_difference": str(exc),
                    "assignment_and_rng_preserved_at_transfer": True}
    with ThreadPoolExecutor(max_workers=min(workers, len(experiment["seeds"]))) as pool:
        records = list(pool.map(run, experiment["seeds"]))
    receipt["replay"] = records
    receipt["interpretation"] = "Same nominal sampler, graph, populations, votes and constraints. Native state continuation is a new documented segment, not a bit-for-bit replay. Validation probe states are excluded from the ensemble."
    receipt_path = destination / "transition_receipt.json"
    with receipt_path.open("x") as stream:
        json.dump(receipt, stream, indent=2, allow_nan=False)
        stream.write("\n")
    if different:
        converted.setdefault("platform_transitions", []).append({"path": str(receipt_path.relative_to(ROOT)),
                                                              "sha256": file_sha256(receipt_path)})
    return converted, records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--exact-only", action="store_true")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--verification-dir", type=Path, default=Path("target_verification"))
    args = parser.parse_args()
    args.verification_dir = args.verification_dir.resolve()
    args.verification_dir.relative_to(ROOT)
    if args.workers < 1:
        raise ValueError("Positive worker count required")
    for name, expected in json.loads((ROOT / "SHA256SUMS.json").read_text()).items():
        path = ROOT / name
        path.resolve().relative_to(ROOT)
        if file_sha256(path) != expected:
            raise ValueError(f"Transfer checksum mismatch: {name}")
    # Keep every pinned analysis and simulation package fixed on native targets.
    for line in (ROOT / "requirements-research-macos-arm64-py312.txt").read_text().splitlines():
        if line and not line.startswith("#"):
            name, version = line.split("==")
            if metadata.version(name) != version:
                raise ValueError(f"Pinned package differs on target: {name}")
    manifest = json.loads((ROOT / "manifest.json").read_text())
    args.verification_dir.mkdir(parents=True, exist_ok=False)
    converted, records, cache = {}, [], {}
    for key, experiment in manifest["experiments"].items():
        value, results = verify_cohort(key, experiment, args.verification_dir / key, args.workers, cache, args.exact_only)
        converted[key] = value
        records.extend(results)
    with (args.verification_dir / "replay_verification.json").open("x") as stream:
        json.dump(records, stream, indent=2, allow_nan=False)
        stream.write("\n")
    with (args.verification_dir / "manifest.json").open("x") as stream:
        json.dump({"source_code": manifest["source_code"], "experiments": converted}, stream, indent=2)
        stream.write("\n")
    if args.verify_only:
        return
    texas = {key: e for key, e in converted.items() if e["state"] == "texas"}
    if set(texas) != {"tx_rebuild", "tx_dispersed"}:
        raise ValueError("Both Texas initialization cohorts required")
    paths = {}
    for key, experiment in texas.items():
        path = args.verification_dir / f"{key}_manifest.json"
        with path.open("x") as stream:
            json.dump({"source_code": manifest["source_code"], "experiments": {key: experiment}}, stream, indent=2)
        paths[key] = path
    subprocess.run([sys.executable, "src/chain/run_texas_matched.py", "--baseline-manifest", str(paths["tx_rebuild"]),
                    "--dispersed-manifest", str(paths["tx_dispersed"]), "--output-dir", "transferred_continuation"], cwd=ROOT, check=True)


if __name__ == "__main__":
    main()
