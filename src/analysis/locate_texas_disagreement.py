"""Locate chain and county differences without removing observations."""

import argparse
import json
from pathlib import Path
import pickle
from types import SimpleNamespace
import sys

import geopandas as gpd
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.analysis.audit_checkpoint_geography import county_summary
from src.analysis.audit_ensemble_chains import load_chain
from src.analysis.audit_rebuild_campaign import METRICS, diagnostics, check_final_checkpoint
from src.chain.benchmark_baselines import checkpoint_path
from src.chain.checkpoint_integrity import file_sha256


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--original-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    for path in (args.manifest, args.original_manifest, args.output_dir):
        path.resolve().relative_to(ROOT)
    manifest = json.loads(args.manifest.read_text())
    e = manifest["experiments"]["tx_rebuild"]
    original = json.loads(args.original_manifest.read_text())["experiments"]["tx_rebuild"]
    directory = ROOT / e["input_dir"]
    registry = json.loads((ROOT / e["config"]).read_text())
    live_checkpoints = ROOT / registry["states"]["texas"]["plans"][e["starting_plan"]]["checkpoint_dir"]
    definition = SimpleNamespace(input_dir=directory, prefix=e["prefix"], epsilon=e["epsilon"],
                                 steps=e["steps"], districts=e["districts"])
    chains = {seed: load_chain(definition, seed) for seed in e["seeds"]}
    if file_sha256(ROOT / e["dataset"]) != e["dataset_sha256"]:
        raise ValueError("Texas dataset changed")
    frame = gpd.read_file(ROOT / e["dataset"], layer="precincts", ignore_geometry=True)
    counties = frame.UNIQUE_ID.str.split("-").str[0]
    if counties.nunique() != 254:
        raise ValueError("County coverage mismatch")
    summaries, contrasts, snapshots, receipts = [], [], [], []
    for metric in METRICS:
        values = {seed: chain.iloc[e["warmup"]:][metric].to_numpy(float) for seed, chain in chains.items()}
        for seed, samples in values.items():
            others = [v for s, v in values.items() if s != seed]
            summaries.append({"metric": metric, "seed": seed, "mean": float(samples.mean()),
                              "mean_minus_other_chains": float(samples.mean() - np.mean(others)),
                              "first_last_1000_difference": float(samples[-1000:].mean() - samples[:1000].mean())})
            contrasts.append({"metric": metric, "omitted_seed_for_attribution_only": seed,
                              **diagnostics(np.stack(others))})
    for seed, chain in chains.items():
        for step in range(100, e["steps"] + 1, 100):
            locations = [checkpoint_path(directory.parent / "checkpoints", e, seed, step),
                         checkpoint_path(live_checkpoints, e, seed, step),
                         checkpoint_path((ROOT / original["input_dir"]).parent / "checkpoints", e, seed, step)]
            paths = [path for path in locations if path.is_file()]
            if not paths or len({file_sha256(path) for path in paths}) != 1:
                raise ValueError("Missing or conflicting checkpoint history")
            path = paths[0]
            with path.open("rb") as stream:
                checkpoint = pickle.load(stream)
            expected = dict(e, steps=step)
            check_final_checkpoint(checkpoint, expected, seed, chain.iloc[:step], manifest["source_code"])
            receipts.append({"path": str(path.relative_to(ROOT)), "sha256": file_sha256(path)})
            if step - 1 < e["warmup"]:
                continue
            summary = county_summary(frame, checkpoint["assignment"], counties)
            summary.insert(0, "seed", seed)
            summary.insert(1, "step", step - 1)
            snapshots.append(summary)
    all_snapshots = pd.concat(snapshots, ignore_index=True)
    means = all_snapshots.groupby(["seed", "county"], as_index=False).agg(
        population=("population", "first"),
        democratic_district_population=("population_in_dem_majority_district", "mean"),
        democratic_district_fraction=("population_fraction_in_dem_majority_district", "mean"),
        district_count=("district_count", "mean"))
    county_contrasts = []
    for row in means.itertuples(index=False):
        others = means[(means.county == row.county) & (means.seed != row.seed)]
        county_contrasts.append({"seed": row.seed, "county": row.county, "population": row.population,
            "democratic_district_population_difference": float(row.democratic_district_population - others.democratic_district_population.mean()),
            "democratic_district_fraction_difference": float(row.democratic_district_fraction - others.democratic_district_fraction.mean()),
            "district_count_difference": float(row.district_count - others.district_count.mean())})
    county_table = pd.DataFrame(county_contrasts)
    county_table["absolute_population_difference"] = county_table.democratic_district_population_difference.abs()
    county_table = county_table.sort_values("absolute_population_difference", ascending=False)
    args.output_dir.mkdir(parents=True, exist_ok=False)
    pd.DataFrame(summaries).to_csv(args.output_dir / "metric_chain_contrasts.csv", index=False, mode="x")
    county_table.to_csv(args.output_dir / "county_chain_contrasts.csv", index=False, mode="x")
    all_snapshots.to_csv(args.output_dir / "county_snapshots.csv", index=False, mode="x")
    report = {"steps_per_chain": e["steps"], "manifest_sha256": file_sha256(args.manifest),
              "metrics": summaries, "leave_one_out_attribution": contrasts,
              "largest_county_contrasts": county_table.head(20).to_dict("records"),
              "checkpoints": receipts,
              "interpretation": "Leave-one-out values locate chain disagreement only; all-chain diagnostics determine freezing. County population in modeled Democratic-majority districts locates associated geographic differences, not a causal or additive decomposition of R-hat. Every saved 100-state checkpoint is used; full-state CSVs determine metric diagnostics."}
    with (args.output_dir / "disagreement.json").open("x") as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write("\n")


if __name__ == "__main__":
    main()
