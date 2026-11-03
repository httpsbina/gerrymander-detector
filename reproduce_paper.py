"""Regenerate registered frozen numerical tables and diagnostic figures."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".venv/matplotlib"))
from src.analysis.freeze_baseline import result_tables
from src.chain.checkpoint_integrity import file_sha256


def reproduce(freeze_path, destination):
    frozen = json.loads(freeze_path.read_text())
    if frozen["status"] != "primary_convergence_frozen":
        raise ValueError("Unfrozen results cannot be reproduced as paper results")
    for name, expected in frozen["checksums"].items():
        path = (ROOT / name).resolve()
        path.relative_to(ROOT)
        if file_sha256(path) != expected:
            raise ValueError(f"Frozen input checksum mismatch: {name}")
    destination.mkdir(parents=True, exist_ok=False)
    for script, directory in (("audit_rebuild_campaign.py", "audit"), ("plot_rebuild_campaign.py", "figures")):
        command = [sys.executable, str(ROOT / "src/analysis" / script), "--manifest",
                   str(ROOT / frozen["manifest"]), "--output-dir", str(destination / directory)]
        with (destination / (directory + ".log")).open("x") as stream:
            subprocess.run(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, check=True)
    report = json.loads((destination / "audit/diagnostics.json").read_text())
    results = result_tables(report, frozen["state"], destination / "audit")
    original = json.loads((freeze_path.parent / "results.json").read_text())
    if results != original:
        raise ValueError("Recomputed numbers differ from the frozen results")
    with (destination / "results.json").open("x") as stream:
        json.dump(results, stream, indent=2, allow_nan=False)
        stream.write("\n")
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=Path("configs/paper_freezes.json"))
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    for path in (args.registry, args.output_dir):
        path.resolve().relative_to(ROOT)
    registry = json.loads(args.registry.read_text())
    if not registry:
        raise ValueError("No frozen state is registered")
    args.output_dir.mkdir(parents=True, exist_ok=False)
    results = {}
    for state, name in registry.items():
        path = (ROOT / name).resolve()
        path.relative_to(ROOT)
        results[state] = reproduce(path, (args.output_dir / state).resolve())
    with (args.output_dir / "results.json").open("x") as stream:
        json.dump(results, stream, indent=2, allow_nan=False)
        stream.write("\n")


if __name__ == "__main__":
    main()
