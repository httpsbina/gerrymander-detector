"""Create immutable audit views at completed continuation boundaries."""

import copy
import json
import os
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]


def snapshot_manifest(manifest, destination):
    destination = Path(destination).resolve()
    destination.relative_to(ROOT)
    destination.mkdir(parents=True, exist_ok=False)
    result = copy.deepcopy(manifest)
    for key, experiment in result["experiments"].items():
        source = (ROOT / experiment["input_dir"]).resolve();source.relative_to(ROOT)
        ensembles = destination / key / "ensembles"
        checkpoints = destination / key / "checkpoints"
        ensembles.mkdir(parents=True);checkpoints.mkdir()
        tag = f"{experiment['epsilon']:g}".replace(".", "p")
        for seed in experiment["seeds"]:
            prefix = f"{experiment['prefix']}_chain_eps{tag}_seed{seed}_steps"
            spans = []
            for path in source.glob(prefix + "*.csv"):
                match = re.fullmatch(re.escape(prefix) + r"(\d+)-(\d+)\.csv", path.name)
                if not match:raise ValueError("Unexpected segment name")
                first, last = map(int, match.groups())
                if last >= experiment["steps"]:
                    if first < experiment["steps"]:raise ValueError("Snapshot boundary cuts through a segment")
                    continue
                spans.append((first, last, path))
            next_step = 0
            for first, last, path in sorted(spans):
                if first != next_step:raise ValueError("Missing or overlapping segment at snapshot boundary")
                (ensembles / path.name).symlink_to(os.path.relpath(path, ensembles));next_step = last + 1
            if next_step != experiment["steps"]:raise ValueError("Snapshot does not cover the full registered chain")
            name = f"{experiment['prefix']}_checkpoint_eps{tag}_seed{seed}_next{experiment['steps']}.pkl"
            checkpoint = source.parent / "checkpoints" / name
            if not checkpoint.is_file():raise FileNotFoundError(checkpoint)
            (checkpoints / name).symlink_to(os.path.relpath(checkpoint, checkpoints))
        experiment["input_dir"] = str(ensembles.relative_to(ROOT))
    path = destination / "manifest.json"
    with path.open("x") as stream:json.dump(result, stream, indent=2);stream.write("\n")
    return path


def screening_status(report, state):
    prefix = "nc_" if state == "north_carolina" else "tx_"
    entries = [value for key, value in report["experiments"].items() if key.startswith(prefix)]
    if state == "north_carolina":entries.append(report["joint_nc"]["nc_block_union"])
    def valid(entry):
        return entry.get("integrity") == "pass" or entry.get("status") == "computed"
    all_primary = bool(entries) and all(valid(entry) and entry.get("diagnostics") and all(
        result["all_finite"] and not result["screening_flags"] for result in entry["diagnostics"].values()
    ) for entry in entries)
    entry = report["joint_nc"]["nc_block_union"] if state == "north_carolina" else report["experiments"].get("tx_rebuild", {})
    seat = entry.get("diagnostics", {}).get("dem_seats", {})
    return {"seat_screen_pass": bool(valid(entry) and seat.get("all_finite") and not seat.get("screening_flags")),
            "all_primary_screens_pass": bool(all_primary)}
