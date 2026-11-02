"""Mechanical continuation check, explicitly separate from research ensembles."""

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--assignment-col", required=True)
    parser.add_argument("--epsilon", type=float, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    for path in (args.dataset, args.output_dir):
        path.resolve().relative_to(ROOT)
    args.output_dir.mkdir(parents=True, exist_ok=False)
    common = [sys.executable, str(ROOT / "src/chain/run_ensemble.py"),
              "--state", "Continuation Probe", "--dataset", str(args.dataset.resolve()),
              "--assignment-col", args.assignment_col, "--population-col", "TOTPOP",
              "--dem-col", "G24PREDHAR", "--rep-col", "G24PRERTRU",
              "--epsilon", str(args.epsilon), "--seed", str(args.seed)]
    env = dict(os.environ, PYTHONHASHSEED="0", PYTHONUNBUFFERED="1")
    commands = []
    tag = f"{args.epsilon:g}".replace(".", "p")
    for name, count, resume in (("whole", 120, False), ("split", 100, False), ("split", 20, True)):
        directory = args.output_dir / name
        command = common + ["--steps", str(count), "--output-dir", str(directory.resolve()),
                            "--checkpoint-dir", str((directory / "checkpoints").resolve())]
        if resume:
            command += ["--resume-from", str((directory / "checkpoints" /
                         f"continuation_probe_checkpoint_eps{tag}_seed{args.seed}_next100.pkl").resolve())]
        started = time.monotonic()
        with (args.output_dir / f"{name}_{count}.log").open("x") as log:
            result = subprocess.run(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
        commands.append({"command": command, "exit_code": result.returncode, "seconds": time.monotonic() - started})
        print(name, count, "exit", result.returncode, "seconds", round(commands[-1]["seconds"], 2), flush=True)
        if result.returncode:
            break
    def rows(folder):
        records = []
        for path in sorted((args.output_dir / folder).glob("*.csv")):
            with path.open() as stream:
                records.extend(csv.DictReader(stream))
        return records
    whole, split = rows("whole"), rows("split")
    passed = len(commands) == 3 and all(row["exit_code"] == 0 for row in commands) and len(whole) == 120 and whole == split
    report = {"purpose": "Continuation mechanics only; never include probe samples in research ensembles",
              "research_ready": False, "exact_continuation_match": passed,
              "whole_rows": len(whole), "split_rows": len(split), "commands": commands,
              "first_differing_step": next((i for i, (left, right) in enumerate(zip(whole, split)) if left != right), None)}
    for name, records in (("whole", whole), ("split", split)):
        report[name + "_rows_sha256"] = hashlib.sha256(json.dumps(records, sort_keys=True).encode()).hexdigest()
    with (args.output_dir / "continuation_report.json").open("x") as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print("Exact continuation:", passed, flush=True)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
