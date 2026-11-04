"""Score existing checkpoint assignments with locally available statewide votes."""

import argparse
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import pickle
import re
from zipfile import ZipFile

import geopandas as gpd
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CAMPAIGN = Path("outputs/analysis/convergence_campaign_2026-11-02")
REBUILD = Path("outputs/analysis/rdh_rebuild_2026-11-02")
OFFICES = {
    "tx": {"G24PRE": "President", "G24USS": "US Senate", "GCCA7": "Criminal appeals 7",
           "GCCA8": "Criminal appeals 8", "GCCAP": "Criminal appeals presiding",
           "GRRC01": "Railroad commissioner", "GSSC02": "Supreme Court 2",
           "GSSC04": "Supreme Court 4", "GSSC06": "Supreme Court 6"},
    "nc": {"G24PRE": "President", "G24ATG": "Attorney general", "G24AUD": "Auditor",
           "G24COA": "Agriculture commissioner", "G24COI": "Insurance commissioner",
           "G24COL": "Labor commissioner", "G24GOV": "Governor", "G24LTG": "Lieutenant governor",
           "G24SOS": "Secretary of state", "G24SPI": "Public instruction superintendent",
           "G24TRE": "Treasurer", "GCAJ12": "Appeals court 12", "GCAJ14": "Appeals court 14",
           "GCAJ15": "Appeals court 15", "GSCJ06": "Supreme Court 6"},
}


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def vote_seats(votes, assignment, districts):
    """Count strict Democratic two-party majorities; ties count as no majority."""
    labels = np.asarray(assignment, dtype=int)
    if set(labels) != set(range(1, districts + 1)) or len(labels) != len(votes):
        raise ValueError("Assignment coverage differs")
    totals = np.stack([votes[labels == district].sum(axis=0)
                       for district in range(1, districts + 1)])
    if (totals.sum(axis=2) <= 0).any():
        raise ValueError("Empty two-party vote district")
    return (totals[:, :, 0] > totals[:, :, 1]).sum(axis=0).astype(int).tolist()


def election_fields(fields, state):
    models = []
    for prefix, name in OFFICES[state].items():
        pair = []
        for party in "DR":
            matches = [field for field in fields if re.fullmatch(re.escape(prefix) + party + r"[A-Z]{3}", field)]
            if len(matches) != 1:
                raise ValueError(f"Missing or ambiguous {prefix} {party}")
            pair.append(matches[0])
        models.append({"office": name, "columns": pair})
    return models


def load_votes(root, state, dataset, records):
    state_name = "texas" if state == "tx" else "north_carolina"
    archive = root / f"data/external/rdh/rebuild_2026-11-02/{state_name}/{state}_2024_gen_2020_blocks_csv.zip"
    master_path = root / REBUILD / f"{state}_block_audit/blocks_master.csv"
    master = pd.read_csv(master_path, dtype={"GEOID20": str, "PRECINCTID": str})
    if master.GEOID20.duplicated().any():
        raise ValueError("Duplicate master block")
    with ZipFile(archive) as zipped:
        with zipped.open(f"{state}_2024_gen_2020_blocks.csv") as stream:
            fields = next(csv.reader(io.TextIOWrapper(stream, encoding="utf-8-sig")))
        models = election_fields(fields, state)
        columns = [column for model in models for column in model["columns"]]
        with zipped.open(f"{state}_2024_gen_2020_blocks.csv") as stream:
            votes = pd.read_csv(stream, usecols=["GEOID20", *columns], dtype={"GEOID20": str})
        readme_hash = hashlib.sha256(zipped.read("README.txt")).hexdigest()
    if votes.GEOID20.duplicated().any() or set(votes.GEOID20) != set(master.GEOID20):
        raise ValueError("Election block coverage differs")
    numeric = votes[columns].to_numpy()
    if not np.isfinite(numeric).all() or (numeric < 0).any() or not (numeric == np.floor(numeric)).all():
        raise ValueError("Invalid block votes")
    merged = master.merge(votes, on="GEOID20", suffixes=("_master", ""), validate="one_to_one")
    for column in models[0]["columns"]:
        if not merged[column].equals(merged[column + "_master"]):
            raise ValueError("Presidential block totals differ from master")
    if state == "tx":
        merged["unit"] = merged.PRECINCTID
    else:
        merged["precinct"] = merged.PRECINCTID.replace({"WAKE-:-01-07 & WAKE-:-01-07A": "WAKE-:-01-07"})
        merged["unit"] = merged.precinct + "|" + merged.DISTRICT_2023.astype(str).str.zfill(2)
        split = merged.groupby("unit").DISTRICT_2025.transform("nunique") > 1
        merged.loc[split, "unit"] += "|25-" + merged.loc[split, "DISTRICT_2025"].astype(str).str.zfill(2)
    units = merged.groupby("unit")[columns].sum()
    frame = gpd.read_file(dataset, layer="precincts", ignore_geometry=True)
    if not frame.UNIQUE_ID.is_unique or set(frame.UNIQUE_ID) != set(units.index):
        raise ValueError("Simulation unit coverage differs")
    units = units.loc[frame.UNIQUE_ID]
    for column in models[0]["columns"]:
        if units[column].tolist() != frame[column].tolist():
            raise ValueError("Node ordering or presidential unit totals differ")
    enacted = {}
    for year in ([2025] if state == "tx" else [2023, 2025]):
        by_district = merged.groupby(f"DISTRICT_{year}")[columns].sum()
        if len(by_district) != (38 if state == "tx" else 14):
            raise ValueError("Missing enacted districts")
        totals = by_district.to_numpy().reshape(len(by_district), len(models), 2)
        if (totals.sum(axis=2) <= 0).any():
            raise ValueError("Empty enacted district")
        enacted[str(year)] = (totals[:, :, 0] > totals[:, :, 1]).sum(axis=0).astype(int).tolist()
    for path in (archive, master_path, dataset): records[str(path.relative_to(root))] = sha(path)
    return units.to_numpy().reshape(len(frame), len(models), 2), models, enacted, {
        "blocks": len(master), "units": len(frame), "readme_sha256": readme_hash,
        "statewide_votes": {column: int(merged[column].sum()) for column in columns},
        "excluded": "District-only legislative and congressional races; nonpartisan yes/no referendum in NC",
    }


def score_group(root, group, spec, votes, models, enacted, records):
    tag = f"{spec['epsilon']:g}".replace(".", "p")
    checkpoint_dirs = [root / CAMPAIGN / group / "checkpoints",
                       root / "outputs/analysis/rebuild_campaign_2026-11-02" / group / "checkpoints"]
    if group == "tx_dispersed":
        checkpoint_dirs = [root / CAMPAIGN / "texas_independent_dispersed/checkpoints"]
    results, plans = [], []
    for seed in spec["seeds"]:
        trace = {}
        pattern = f"{spec['prefix']}_chain_eps{tag}_seed{seed}_steps*.csv"
        for path in sorted((root / spec["input_dir"]).glob(pattern)):
            first = int(re.search(r"steps(\d+)-", path.name)[1])
            if first >= spec["steps"]: continue
            records[str(path.relative_to(root))] = sha(path)
            with path.open() as stream:
                for row in csv.DictReader(stream):
                    step = int(row["step"])
                    if step >= spec["steps"]: continue
                    if step in trace: raise ValueError("Overlapping trace steps")
                    trace[step] = row
        if set(trace) != set(range(spec["steps"])): raise ValueError("Incomplete trace")
        scores = []
        reference_provenance = None
        for boundary in range(100, spec["steps"] + 1, 100):
            if boundary - 1 < spec["warmup"]: continue
            name = f"{spec['prefix']}_checkpoint_eps{tag}_seed{seed}_next{boundary}.pkl"
            paths = [directory / name for directory in checkpoint_dirs if (directory / name).is_file()]
            if not paths: raise ValueError(f"Missing checkpoint {name}")
            hashes = {sha(path) for path in paths}
            if len(hashes) != 1: raise ValueError("Conflicting checkpoint copies")
            path = paths[0]; records[str(path.relative_to(root))] = next(iter(hashes))
            with path.open("rb") as stream: checkpoint = pickle.load(stream)
            if checkpoint["version"] != 2 or checkpoint["seed"] != seed or checkpoint["next_step"] != boundary:
                raise ValueError("Checkpoint identity differs")
            provenance = checkpoint["provenance"]
            if reference_provenance is None: reference_provenance = provenance
            if provenance != reference_provenance: raise ValueError("Checkpoint provenance changed")
            if provenance["dataset_sha256"] != spec["dataset_sha256"]:
                raise ValueError("Checkpoint dataset differs")
            for key, name in [("runner_sha256", "src/chain/run_ensemble.py"),
                              ("checkpoint_code_sha256", "src/chain/checkpoint_integrity.py")]:
                if provenance[key] != sha(root / name): raise ValueError("Checkpoint source differs")
            config = provenance["configuration"]
            if config["epsilon"] != spec["epsilon"] or config["node_repeats"] != spec["node_repeats"] or config["sample_every"] != 1:
                raise ValueError("Checkpoint configuration differs")
            assignment = checkpoint["assignment"]
            if set(assignment) != set(range(len(votes))): raise ValueError("Checkpoint node IDs differ")
            row = trace[boundary - 1]
            if checkpoint["plan_hash"] != row["plan_hash"]: raise ValueError("Checkpoint plan differs from trace")
            seat_counts = vote_seats(votes, [assignment[node] for node in range(len(votes))], spec["districts"])
            if seat_counts[0] != int(row["dem_seats"]): raise ValueError("Presidential replay score differs")
            scores.append(seat_counts)
            plans.append({"group": group, "seed": seed, "step": boundary - 1, "plan_hash": checkpoint["plan_hash"],
                          **{model["office"]: count for model, count in zip(models, seat_counts)}})
        array = np.asarray(scores)
        results.append({"seed": seed, "checkpoints": len(scores),
                        "mean_democratic_seats": array.mean(axis=0).tolist(),
                        "seat_sums": array.sum(axis=0).astype(int).tolist(),
                        "at_or_below_enacted": {year: (array <= values).sum(axis=0).astype(int).tolist()
                                                for year, values in enacted.items()}})
        print(group, seed, len(scores), flush=True)
    total = sum(row["checkpoints"] for row in results)
    return {"states_per_chain": spec["steps"], "warmup": spec["warmup"], "checkpoints": total,
            "chains": results, "mean_democratic_seats": [sum(row["seat_sums"][i] for row in results) / total for i in range(len(models))],
            "at_or_below_enacted": {year: [sum(row["at_or_below_enacted"][year][i] for row in results)
                                           for i in range(len(models))] for year in enacted}}, plans


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    root = args.source_root.resolve()
    destination = args.output_dir.resolve(); destination.relative_to(ROOT)
    if destination.exists(): raise FileExistsError(destination)
    records, report, all_plans = {}, {}, []
    for state, manifest in [("tx", CAMPAIGN / "tx_shared45000_continuation_20261103/shared_prefix_045000/manifest.json"),
                            ("nc", Path("outputs/analysis/convergence_campaign_2026-11-02/nc_primary_continuation/snapshot_003/manifest.json"))]:
        records[str(manifest)] = sha(root / manifest)
        experiments = json.loads((root / manifest).read_text())["experiments"]
        groups = {}; baseline = next(iter(experiments.values()))
        votes, models, enacted, inventory = load_votes(root, state, root / baseline["dataset"], records)
        for group, spec in experiments.items():
            if sha(root / spec["dataset"]) != spec["dataset_sha256"]: raise ValueError("Dataset changed")
            group_votes, other_models, other_enacted, _ = load_votes(root, state, root / spec["dataset"], records)
            if models != other_models or enacted != other_enacted: raise ValueError("Election definitions differ")
            groups[group], plans = score_group(root, group, spec, group_votes, models, enacted, records)
            all_plans.extend({"state": state, **plan} for plan in plans)
        report[state] = {"models": models, "enacted_seats": enacted, "inventory": inventory, "groups": groups}
    destination.mkdir(parents=True)
    result = {"process_nice": os.getpriority(os.PRIO_PROCESS, 0), "checkpoint_interval": 100,
              "state_definition": "Checkpoint next_step N contains recorded state N-1; use every available 100-state checkpoint after the unchanged warmup.",
              "results": report, "input_checksums": records, "code_sha256": sha(__file__)}
    (destination / "results.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    (destination / "checkpoint_scores.json").write_text(json.dumps(all_plans, indent=2, allow_nan=False) + "\n")
    print(destination)


if __name__ == "__main__":
    main()
