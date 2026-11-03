"""Compare county-restricted partitions in the Texas and NC baseline chains."""

import argparse
import json
from pathlib import Path
import pickle
import sys

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.analysis.audit_partition_distances import coded_distances, lag_group
from src.chain.checkpoint_integrity import file_sha256


def county_masks(counties, population, minimum):
    counties = pd.Series(counties)
    population = np.asarray(population, dtype=float)
    if (len(counties) != len(population) or counties.isna().any() or (counties.astype(str).str.len() == 0).any()
            or not np.isfinite(population).all() or (population < 0).any() or minimum <= 0):
        raise ValueError("Invalid county coverage, population or selection threshold")
    coverage, masks = [], {}
    for county in sorted(counties.unique()):
        mask = counties.to_numpy() == county
        total = float(population[mask].sum())
        selected = total >= minimum
        coverage.append({"county": str(county), "population": total, "units": int(mask.sum()),
                         "zero_population_units": int((population[mask] == 0).sum()), "selected": selected})
        if selected:
            masks[str(county)] = mask
    return coverage, masks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--checkpoint-audit", type=Path, required=True)
    parser.add_argument("--global-analysis-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--minimum-county-population", type=int, default=500000)
    args = parser.parse_args()
    for p in (args.manifest, args.checkpoint_audit, args.global_analysis_dir, args.output_dir):
        p.resolve().relative_to(ROOT)
    if args.output_dir.exists():
        raise FileExistsError("Refusing existing county partition-distance output directory")
    manifest = json.loads(args.manifest.read_text())
    audit = json.loads(args.checkpoint_audit.read_text())
    global_report = json.loads((args.global_analysis_dir / "partition_distances.json").read_text())
    if audit["manifest_sha256"] != file_sha256(args.manifest) or global_report["manifest_sha256"] != audit["manifest_sha256"]:
        raise ValueError("Analysis inputs refer to different campaigns")
    receipts = {}
    for row in audit["checkpoints"]:
        p = Path(row["path"]).resolve();p.relative_to(ROOT);receipts[p] = row["sha256"]
    args.output_dir.mkdir(parents=True, exist_ok=False)
    summaries, coverage_rows, contrasts, conditions = [], [], [], []
    definitions = {"tx_rebuild": ["tx_rebuild"], "nc_block_union": ["nc_block_union_2023", "nc_block_union_2025"]}
    for condition, keys in definitions.items():
        first = manifest["experiments"][keys[0]]
        dataset = (ROOT / first["dataset"]).resolve();dataset.relative_to(ROOT)
        if file_sha256(dataset) != first["dataset_sha256"]:
            raise ValueError("Dataset differs from campaign fingerprint")
        county_column = "UNIQUE_ID" if first["state"] == "texas" else "PRECINCT_KEY"
        frame = gpd.read_file(dataset, layer="precincts", columns=["TOTPOP", county_column], ignore_geometry=True)
        separator = "-" if first["state"] == "texas" else "-:-"
        counties = frame[county_column].str.split(separator).str[0]
        expected_count = 254 if first["state"] == "texas" else 100
        if counties.nunique() != expected_count:
            raise ValueError("County coverage differs from source audit")
        population = frame.TOTPOP.to_numpy(float)
        coverage, masks = county_masks(counties, population, args.minimum_county_population)
        coverage_rows.extend({"condition": condition, **row} for row in coverage)
        plans, locations = [], {}
        for key in keys:
            e = manifest["experiments"][key]
            if any(e[name] != first[name] for name in ("dataset_sha256", "epsilon", "node_repeats", "steps", "warmup")):
                raise ValueError("Incompatible starting-map groups")
            directory = (ROOT / e["input_dir"]).resolve().parent / "checkpoints";directory.relative_to(ROOT)
            tag = f"{e['epsilon']:g}".replace(".", "p")
            for seed in e["seeds"]:
                for next_step in sorted(set(range(100, e["steps"] + 1, 100)) | {e["steps"]}):
                    p = directory / f"{e['prefix']}_checkpoint_eps{tag}_seed{seed}_next{next_step}.pkl"
                    if receipts.get(p) != file_sha256(p):
                        raise ValueError("Checkpoint differs from complete fingerprint audit")
                    with p.open("rb") as stream:c = pickle.load(stream)
                    if (c["version"] != 2 or c["seed"] != seed or c["next_step"] != next_step
                            or c["epsilon"] != e["epsilon"] or c["node_repeats"] != e["node_repeats"]
                            or c["provenance"]["dataset_sha256"] != first["dataset_sha256"]
                            or c["provenance"]["runner_sha256"] != manifest["source_code"]["src/chain/run_ensemble.py"]
                            or c["provenance"]["checkpoint_code_sha256"] != manifest["source_code"]["src/chain/checkpoint_integrity.py"]
                            or set(c["assignment"]) != set(frame.index)):
                        raise ValueError("Checkpoint provenance or node coverage mismatch")
                    labels = np.asarray([str(c["assignment"][i]) for i in frame.index])
                    location = (seed, next_step - 1)
                    if location in locations:raise ValueError("Duplicate checkpoint location")
                    locations[location] = len(plans)
                    plans.append({"labels": labels, "starting_plan": e["starting_plan"]})
        pair_file = args.global_analysis_dir / f"{condition}_pairs.csv"
        pairs = pd.read_csv(pair_file)
        indices, seen = [], set()
        for row in pairs.itertuples(index=False):
            a, b = locations[(row.left_seed, row.left_step)], locations[(row.right_seed, row.right_step)]
            canonical = tuple(sorted((a, b)))
            if a == b or canonical in seen:raise ValueError("Repeated or self comparison")
            seen.add(canonical);indices.append((a, b))
            if (row.step_lag != abs(row.left_step - row.right_step)
                    or row.lag_group != lag_group(row.step_lag)
                    or row.same_chain != (row.left_seed == row.right_seed)
                    or row.same_starting_plan != (plans[a]["starting_plan"] == plans[b]["starting_plan"])
                    or row.both_post_warmup != (min(row.left_step, row.right_step) >= first["warmup"])):
                raise ValueError("Pair metadata does not match checkpoints")
        if len(seen) != len(plans) * (len(plans) - 1) // 2:
            raise ValueError("Pair table does not cover every checkpoint pair")
        groups = ["both_post_warmup", "same_chain", "same_starting_plan", "lag_group"]
        for county, mask in masks.items():
            codes = [np.unique(plan["labels"][mask], return_inverse=True)[1] for plan in plans]
            sizes = [int(code.max()) + 1 for code in codes]
            values = [coded_distances(codes[a], codes[b], sizes[a], sizes[b], population[mask]) for a, b in indices]
            table = pairs[groups + ["step_lag"]].copy()
            table[["unit_vi_bits", "population_vi_bits"]] = values
            for group, part in table.groupby(groups):
                result = dict(zip(groups, group));result.update(condition=condition, county=county, pairs=len(part))
                for metric in ("unit_vi_bits", "population_vi_bits"):
                    result[metric + "_mean"] = float(part[metric].mean())
                    result[metric + "_median"] = float(part[metric].median())
                summaries.append(result)
            long = table[table.both_post_warmup & (table.step_lag >= 2000)]
            within = long[long.same_chain]
            contrast = {"condition": condition, "county": county, "population": int(population[mask].sum()),
                        "within_chain_population_vi_bits": float(within.population_vi_bits.mean()), "within_chain_pairs": len(within)}
            lag_weights = within.step_lag.value_counts(normalize=True).sort_index()
            for same, label in ((True, "between_same_start"), (False, "between_different_starts")):
                between = long[(~long.same_chain) & (long.same_starting_plan == same)]
                contrast[label + "_pairs"] = len(between)
                if len(between):
                    np.testing.assert_allclose(lag_weights, between.step_lag.value_counts(normalize=True).sort_index(), rtol=0, atol=1e-14)
                    contrast[label + "_population_vi_bits"] = float(between.population_vi_bits.mean())
                    contrast[label + "_minus_within_bits"] = float(between.population_vi_bits.mean() - within.population_vi_bits.mean())
            contrasts.append(contrast)
            print(condition, county, "complete", flush=True)
        conditions.append({"condition": condition, "dataset_sha256": first["dataset_sha256"], "checkpoint_count": len(plans),
                           "selected_counties": len(masks), "pair_file_sha256": file_sha256(pair_file), "comparisons_per_county": len(pairs)})
    pd.DataFrame(coverage_rows).to_csv(args.output_dir / "county_coverage.csv", index=False, mode="x")
    pd.DataFrame(summaries).to_csv(args.output_dir / "county_distance_summary.csv", index=False, mode="x")
    contrasts = pd.DataFrame(contrasts)
    contrasts.to_csv(args.output_dir / "long_lag_contrasts.csv", index=False, mode="x")
    for condition, part in contrasts.groupby("condition"):
        x = np.arange(len(part));fig, ax = plt.subplots(figsize=(10, 5))
        ax.bar(x - 0.25, part.within_chain_population_vi_bits, width=0.25, label="Within chain")
        ax.bar(x, part.between_same_start_population_vi_bits, width=0.25, label="Between chains, same starting map")
        if "between_different_starts_population_vi_bits" in part and part.between_different_starts_population_vi_bits.notna().any():
            ax.bar(x + 0.25, part.between_different_starts_population_vi_bits, width=0.25, label="Between starting maps")
        ax.set_xticks(x, part.county, rotation=45, ha="right");ax.set_ylabel("County population-weighted VI (bits)")
        ax.set_title(condition.replace("_", " ") + f" | counties with population ≥{args.minimum_county_population:,}")
        ax.legend(frameon=False, fontsize=8);fig.tight_layout();fig.savefig(args.output_dir / f"{condition}_county_distances.png", dpi=160);plt.close(fig)
    report = {"manifest_sha256": file_sha256(args.manifest), "checkpoint_audit_sha256": file_sha256(args.checkpoint_audit),
              "analysis_code_sha256": file_sha256(__file__), "distance_code_sha256": file_sha256(ROOT / "src/analysis/audit_partition_distances.py"),
              "minimum_county_population": args.minimum_county_population, "conditions": conditions,
              "primary_comparison": "Both snapshots after the configured 500-state warmup, step lag at least 2000, matching lag distributions",
              "measure": "Variation of information restricted to county units; unit measure includes zero-population units, population measure gives them zero mass"}
    with (args.output_dir / "county_partition_distances.json").open("x") as stream:json.dump(report, stream, indent=2, allow_nan=False);stream.write("\n")


if __name__ == "__main__":
    main()
