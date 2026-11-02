"""Locate geographic differences using every saved campaign checkpoint.

Checkpoint snapshots are diagnostic views, not extra independent observations
or replacements for full-state convergence analysis.
"""

import argparse
import json
from pathlib import Path
import pickle
import sys

import geopandas as gpd
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.chain.checkpoint_integrity import file_sha256


def county_summary(frame, assignment, counties):
    if set(assignment) != set(frame.index):
        raise ValueError("Checkpoint nodes differ from dataset rows")
    part = frame[["TOTPOP", "G24PREDHAR", "G24PRERTRU"]].copy()
    part["district"] = [assignment[index] for index in frame.index]
    part["county"] = list(counties)
    votes = part.groupby("district")[["G24PREDHAR", "G24PRERTRU"]].sum()
    democratic = set(votes.index[votes.G24PREDHAR > votes.G24PRERTRU])
    part["population_in_dem_majority_district"] = part.TOTPOP * part.district.isin(democratic)
    result = part.groupby("county").agg(
        population=("TOTPOP", "sum"), units=("district", "size"),
        district_count=("district", "nunique"),
        population_in_dem_majority_district=("population_in_dem_majority_district", "sum"),
    ).reset_index()
    if (result.population <= 0).any():
        raise ValueError("Nonpositive county population; population fraction undefined")
    result["population_fraction_in_dem_majority_district"] = (
        result.population_in_dem_majority_district / result.population)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--experiments", nargs="+")
    args = parser.parse_args()
    for path in (args.manifest, args.output_dir):
        path.resolve().relative_to(ROOT)
    if args.output_dir.exists():
        raise FileExistsError("Refusing existing checkpoint geography audit")
    manifest = json.loads(args.manifest.read_text())
    selected = args.experiments or list(manifest["experiments"])
    if set(selected) - set(manifest["experiments"]):
        raise ValueError("Unknown experiment")
    snapshots, receipts = [], []
    for key in selected:
        experiment = manifest["experiments"][key]
        dataset = (ROOT / experiment["dataset"]).resolve()
        dataset.relative_to(ROOT)
        if file_sha256(dataset) != experiment["dataset_sha256"]:
            raise ValueError("Dataset hash differs from manifest")
        frame = gpd.read_file(dataset, layer="precincts")
        if experiment["state"] == "texas":
            counties = frame.UNIQUE_ID.str.split("-").str[0]
            if not counties.str.fullmatch(r"\d{3}").all() or counties.nunique() != 254:
                raise ValueError("Unrecognized Texas county IDs")
        else:
            counties = frame.PRECINCT_KEY.str.split("-:-").str[0]
            if counties.nunique() != 100:
                raise ValueError("Unexpected NC county coverage")
        directory = (ROOT / experiment["input_dir"]).resolve().parent / "checkpoints"
        directory.relative_to(ROOT)
        tag = f"{experiment['epsilon']:g}".replace(".", "p")
        for seed in experiment["seeds"]:
            prefix = f"{experiment['prefix']}_checkpoint_eps{tag}_seed{seed}_next"
            files = sorted(directory.glob(prefix + "*.pkl"), key=lambda path: int(path.stem.split("_next")[-1]))
            expected = sorted(set(range(100, experiment["steps"] + 1, 100)) | {experiment["steps"]})
            if [int(path.stem.split("_next")[-1]) for path in files] != expected:
                raise ValueError("Missing or unexpected checkpoint snapshots")
            for path, next_step in zip(files, expected):
                with path.open("rb") as stream:
                    checkpoint = pickle.load(stream)
                provenance = checkpoint["provenance"]
                if (checkpoint.get("version") != 2 or checkpoint["seed"] != seed
                        or checkpoint["next_step"] != next_step
                        or checkpoint["epsilon"] != experiment["epsilon"]
                        or checkpoint["node_repeats"] != experiment["node_repeats"]
                        or provenance["dataset_sha256"] != experiment["dataset_sha256"]
                        or provenance["runner_sha256"] != manifest["source_code"]["src/chain/run_ensemble.py"]):
                    raise ValueError("Checkpoint provenance or parameter mismatch")
                result = county_summary(frame, checkpoint["assignment"], counties)
                result.insert(0, "experiment", key)
                result.insert(1, "seed", seed)
                result.insert(2, "step", next_step - 1)
                result.insert(3, "post_warmup", next_step - 1 >= experiment["warmup"])
                snapshots.append(result)
                receipts.append({"path": str(path), "sha256": file_sha256(path)})
    snapshots = pd.concat(snapshots, ignore_index=True)
    summaries = []
    for (key, seed, county), part in snapshots[snapshots.post_warmup].groupby(["experiment", "seed", "county"]):
        values = part.population_fraction_in_dem_majority_district.to_numpy(float)
        summaries.append({"experiment": key, "seed": seed, "county": county,
                          "snapshots": len(part), "population": int(part.population.iloc[0]),
                          "mean_population_fraction_in_dem_majority_district": float(values.mean()),
                          "min_population_fraction": float(values.min()), "max_population_fraction": float(values.max()),
                          "last_minus_first_ten_snapshot_mean": float(values[-10:].mean() - values[:10].mean()),
                          "mean_district_count": float(part.district_count.mean())})
    summary = pd.DataFrame(summaries)
    ranges = []
    metric = "mean_population_fraction_in_dem_majority_district"
    for (key, county), part in summary.groupby(["experiment", "county"]):
        ranges.append({"experiment": key, "county": county, "population": int(part.population.iloc[0]),
                       "across_seed_mean_fraction_range": float(part[metric].max() - part[metric].min())})
    ranges = pd.DataFrame(ranges).sort_values(["experiment", "across_seed_mean_fraction_range"], ascending=[True, False])
    if not np.isfinite(summary.select_dtypes(include="number").to_numpy()).all():
        raise ValueError("Nonfinite geographic summary")
    args.output_dir.mkdir(parents=True, exist_ok=False)
    snapshots.to_csv(args.output_dir / "county_snapshots.csv", index=False, mode="x")
    summary.to_csv(args.output_dir / "county_chain_summary.csv", index=False, mode="x")
    ranges.to_csv(args.output_dir / "county_chain_ranges.csv", index=False, mode="x")
    report = {"research_ready": False, "manifest_sha256": file_sha256(args.manifest),
              "checkpoint_snapshots": len(receipts), "county_snapshot_rows": len(snapshots),
              "interpretation": "Population fractions locate geographic chain differences under modeled presidential votes; they are not congressional outcomes, legal findings, or calibrated uncertainty",
              "sampling": "Every saved 100-state checkpoint plus any final checkpoint, including warmup; no snapshots substitute for the complete chain diagnostics",
              "county_membership": "Dataset precinct county identifiers; inherits RDH block-to-precinct membership assumptions",
              "checkpoints": receipts}
    with (args.output_dir / "geography_audit.json").open("x") as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({key: value for key, value in report.items() if key != "checkpoints"}, indent=2))


if __name__ == "__main__":
    main()
