"""Run protected continuation blocks and record their measured throughput."""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import copy
import json
import os
from pathlib import Path
import pickle
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".venv/matplotlib"))
import numpy as np
import pandas as pd
from src.chain.benchmark_baselines import checkpoint_path
from src.chain.checkpoint_integrity import file_sha256
from src.analysis.audit_rebuild_campaign import check_final_checkpoint
from src.chain.convergence_state import screening_status, snapshot_manifest


def run_wave(manifest, jobs, lengths, destination, workers):
    destination.mkdir(parents=True, exist_ok=False)
    for name in ("src/chain/run_ensemble.py", "src/chain/checkpoint_integrity.py"):
        if file_sha256(ROOT / name) != manifest["source_code"][name]:
            raise ValueError("Baseline implementation fingerprint changed")
    env = dict(os.environ, PYTHONHASHSEED="0", PYTHONUNBUFFERED="1", OMP_NUM_THREADS="1",
               OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1", MPLCONFIGDIR=str(ROOT / ".venv/matplotlib"))
    def run(job):
        key, seed, count = job
        e = manifest["experiments"][key]
        start = lengths[(key, seed)]
        directory = (ROOT / e["input_dir"]).resolve();directory.relative_to(ROOT)
        checkpoint = checkpoint_path(directory.parent / "checkpoints", e, seed, start)
        configuration = e.get("seed_configs", {}).get(str(seed), e["config"])
        command = [sys.executable, str(ROOT / "main.py"), "--nc" if e["state"] == "north_carolina" else "--texas",
                   "--year", e["starting_plan"], "--config", str(ROOT / configuration),
                   "--stage", "simulate", "--steps", str(count), "--seed", str(seed)]
        if start:
            command.extend(["--resume-from", str(checkpoint)])
        started = time.monotonic()
        with (destination / f"{key}_seed{seed}.log").open("x") as log:
            result = subprocess.run(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
        seconds = time.monotonic() - started
        record = {"experiment": key, "seed": seed, "first_step": start, "new_states": count,
                  "seconds": seconds, "steps_per_hour": 3600 * count / seconds, "exit_code": result.returncode,
                  "command": [p.replace(str(ROOT) + "/", "") for p in command]}
        if result.returncode == 0:
            try:
                tag = f"{e['epsilon']:g}".replace(".", "p")
                csv = directory / f"{e['prefix']}_chain_eps{tag}_seed{seed}_steps{start:06d}-{start+count-1:06d}.csv"
                frame = pd.read_csv(csv)
                if frame.step.tolist() != list(range(start, start + count)):
                    raise ValueError("Unexpected segment coverage")
                if not np.isfinite(frame[["dem_seats","efficiency_gap","cut_edges","mean_median","max_abs_pop_dev"]].to_numpy()).all():
                    raise ValueError("Nonfinite simulation output")
                if not (frame.seed == seed).all() or not (frame.max_abs_pop_dev <= e["epsilon"] + 1e-10).all():
                    raise ValueError("Seed or population constraint mismatch")
                final = checkpoint_path(directory.parent / "checkpoints", e, seed, start + count)
                with final.open("rb") as stream: c = pickle.load(stream)
                expected = copy.deepcopy(e);expected["steps"] = start + count
                check_final_checkpoint(c, expected, seed, frame, manifest["source_code"])
                if "expected_checkpoint_provenance" in e:
                    if c["provenance"] != e["expected_checkpoint_provenance"][str(seed)]:
                        raise ValueError("Registered starting-map provenance mismatch")
                    if start == 0 and frame.plan_hash.iloc[0] != e["starting_plan_hashes"][str(seed)]:
                        raise ValueError("Registered initial assignment mismatch")
                record.update(csv=str(csv.relative_to(ROOT)), csv_sha256=file_sha256(csv), checkpoint_sha256=file_sha256(final))
            except Exception as exc:
                record["validation_error"] = f"{type(exc).__name__}: {exc}"
        with (destination / f"{key}_seed{seed}.json").open("x") as stream:
            json.dump(record, stream, indent=2);stream.write("\n")
        return record
    start = time.monotonic()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        records = [future.result() for future in as_completed([pool.submit(run, job) for job in jobs])]
    elapsed = time.monotonic() - start
    result = {"workers": workers, "seconds": elapsed, "states": sum(job[2] for job in jobs),
              "aggregate_steps_per_hour": 3600 * sum(job[2] for job in jobs) / elapsed, "jobs": records}
    with (destination / "timing.json").open("x") as stream:json.dump(result, stream, indent=2);stream.write("\n")
    failures = [r for r in records if r["exit_code"] or "validation_error" in r]
    if failures:
        raise RuntimeError("Continuation block failed; inspect preserved logs and validation records")
    for key, seed, count in jobs:lengths[(key, seed)] += count
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--full-load-benchmark", action="store_true")
    parser.add_argument("--state", choices=("nc", "texas"))
    parser.add_argument("--target", choices=("seats", "primary"), default="primary")
    parser.add_argument("--block-states", type=int, default=1000)
    parser.add_argument("--rounds", type=int, default=20)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--stop-file", type=Path)
    args = parser.parse_args()
    for p in (args.manifest, args.output_dir, args.stop_file):
        if p is not None:p.resolve().relative_to(ROOT)
    manifest = json.loads(args.manifest.read_text())
    destination = args.output_dir.resolve();destination.mkdir(parents=True, exist_ok=False)
    if not args.full_load_benchmark:
        if args.state is None or min(args.block_states, args.rounds, args.workers) < 1:
            raise ValueError("Select a state and positive block size, round count and worker count")
        state = "north_carolina" if args.state == "nc" else "texas"
        manifest["experiments"] = {key:e for key,e in manifest["experiments"].items() if e["state"] == state}
        if not manifest["experiments"]:raise ValueError("No selected-state experiments")
        lengths = {(key, seed):e["steps"] for key,e in manifest["experiments"].items() for seed in e["seeds"]}
        for index in range(1, args.rounds + 1):
            if args.stop_file is not None and args.stop_file.exists():
                print("Stop requested at completed segment boundary", flush=True);return
            jobs = [(key, seed, args.block_states) for key,e in manifest["experiments"].items() for seed in e["seeds"]]
            run_wave(manifest, jobs, lengths, destination / f"round_{index:03d}", args.workers)
            for e in manifest["experiments"].values():e["steps"] += args.block_states
            live = destination / f"manifest_{index:03d}.json"
            with live.open("x") as stream:json.dump(manifest, stream, indent=2);stream.write("\n")
            snapshot = snapshot_manifest(manifest, destination / f"snapshot_{index:03d}")
            audit_dir = destination / f"audit_{index:03d}"
            env = dict(os.environ, MPLCONFIGDIR=str(ROOT / ".venv/matplotlib"))
            command = [sys.executable, str(ROOT / "src/analysis/audit_rebuild_campaign.py"),
                       "--manifest", str(snapshot), "--output-dir", str(audit_dir)]
            with (destination / f"audit_{index:03d}.log").open("x") as stream:
                result = subprocess.run(command, cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT)
            if result.returncode:raise RuntimeError("Audit execution failed")
            report = json.loads((audit_dir / "diagnostics.json").read_text())
            if any(entry["integrity"] != "pass" for entry in report["experiments"].values()):
                raise RuntimeError("Unexpected chain integrity failure; continuation stopped for review")
            if any(not value["all_finite"] for entry in report["experiments"].values() for value in entry["diagnostics"].values()):
                raise RuntimeError("Unexpected nonfinite primary diagnostic; continuation stopped for review")
            status = screening_status(report, state)
            status.update(steps_per_chain={key:e["steps"] for key,e in manifest["experiments"].items()},
                          joint=report["joint_nc"].get("nc_block_union", {}) if args.state == "nc" else report["experiments"]["tx_rebuild"])
            with (destination / f"status_{index:03d}.json").open("x") as stream:json.dump(status, stream, indent=2);stream.write("\n")
            print(json.dumps({"steps_per_chain": status["steps_per_chain"],
                              "seat_screen_pass": status["seat_screen_pass"],
                              "all_primary_screens_pass": status["all_primary_screens_pass"],
                              "metrics": {name:{key:value[key] for key in ("rank_split_rhat","bulk_ess","tail_ess","ess_screening_minimum")}
                                          for name,value in status["joint"].get("diagnostics", {}).items()}}), flush=True)
            if status["seat_screen_pass" if args.target == "seats" else "all_primary_screens_pass"]:
                print("Requested numerical screens passed", flush=True);return
        print("Round budget reached; numerical target remains pending", flush=True)
        return
    lengths = {(key, seed): e["steps"] for key,e in manifest["experiments"].items() for seed in e["seeds"]}
    nc = [(key, seed, 1000) for key,e in manifest["experiments"].items() if e["state"] == "north_carolina" for seed in e["seeds"]]
    tx = [("tx_rebuild", seed, 200) for seed in manifest["experiments"]["tx_rebuild"]["seeds"]]
    measurements = []
    for index, pair in enumerate((tx[:2], tx[2:]), 1):
        result = run_wave(manifest, nc + pair, lengths, destination / f"wave_{index}", 8)
        measurements.append(result)
        print(json.dumps({k:v for k,v in result.items() if k != "jobs"}), flush=True)
    for key,e in manifest["experiments"].items():
        sizes = {lengths[(key, seed)] for seed in e["seeds"]}
        if len(sizes) != 1:raise ValueError("Unequal final lengths")
        e["steps"] = sizes.pop()
    with (destination / "manifest.json").open("x") as stream:json.dump(manifest, stream, indent=2);stream.write("\n")
    with (destination / "throughput.json").open("x") as stream:json.dump({"phases":measurements},stream,indent=2);stream.write("\n")


if __name__ == "__main__":
    main()
