"""Build a Texas candidate with the five explicitly authorized ring repairs."""

import argparse
import json
from pathlib import Path
import sys

import geopandas as gpd
import pandas as pd
import shapely

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.validation.audit_rdh_geometry import inspect_geometry
from src.validation.audit_rdh_sources import sha256

AUTHORIZED_REPAIRS = {"121-4222", "295-0106", "401-0416", "453-0152", "479-0252"}
AUTHORIZED_SOURCE_SHA256 = "c60db2902065214bee5345923a1222870c4f0234a4689c545699b60a2d6b1a69"
METRICS = ["TOTPOP", "G24PREDHAR", "G24PRERTRU"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--block-master", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    for path in (args.source_root, args.block_master, args.output_dir):
        path.resolve().relative_to(ROOT)
    if args.output_dir.exists():
        raise FileExistsError("Refusing existing Texas candidate directory")
    source = (args.source_root / "texas/tx_2024_gen_tx_vtd.zip").resolve()
    if sha256(source) != AUTHORIZED_SOURCE_SHA256:
        raise ValueError("Texas source differs from the reviewed repair proposal")
    shapes = {}
    for category in ("all", "cong"):
        stem = f"tx_2024_gen_{category}_tx_vtd"
        columns = ["UNIQUE_ID", "CONG_DIST"] if category == "cong" else ["UNIQUE_ID"]
        shapes[category] = gpd.read_file(f"/vsizip/{source}/{stem}/{stem}.shp", columns=columns)
    geometry = shapes["all"]
    invalid = set(geometry.loc[~geometry.geometry.is_valid, "UNIQUE_ID"])
    if invalid != AUTHORIZED_REPAIRS:
        raise ValueError(f"Source defects differ from authorized repair set: {invalid}")
    repairs = []
    for index in geometry.index[~geometry.geometry.is_valid]:
        original = geometry.at[index, "geometry"]
        repaired = shapely.make_valid(original)
        if not repaired.is_valid or repaired.geom_type != "Polygon":
            raise ValueError("Authorized ring repair did not produce a valid polygon")
        displacement = float(original.hausdorff_distance(repaired))
        repairs.append({"id": geometry.at[index, "UNIQUE_ID"],
                        "original_reason": shapely.is_valid_reason(original),
                        "operation": "shapely.make_valid; user approved five candidate-only repairs",
                        "area_change_m2": repaired.area - original.area,
                        "hausdorff_distance_m": displacement})
        if displacement != 0:
            raise ValueError("Repair displaced a boundary; outside reviewed proposal")
        geometry.at[index, "geometry"] = repaired
    blocks = pd.read_csv(args.block_master, dtype={"GEOID20": str, "PRECINCTID": str})
    if len(blocks) != 668757 or not blocks.GEOID20.is_unique:
        raise ValueError("Invalid Texas block coverage")
    aggregate = blocks.groupby("PRECINCTID").agg(
        BLOCK_COUNT=("GEOID20", "size"), TOTPOP=("TOTPOP", "sum"),
        G24PREDHAR=("G24PREDHAR", "sum"), G24PRERTRU=("G24PRERTRU", "sum"),
        PLANC2333_DISTRICTS=("DISTRICT_2025", "nunique"),
    ).reset_index()
    seed = shapes["cong"][["UNIQUE_ID", "CONG_DIST"]].copy()
    seed["CONG_DIST"] = seed.CONG_DIST.astype(str).str.zfill(2)
    if not geometry.UNIQUE_ID.is_unique or not seed.UNIQUE_ID.is_unique:
        raise ValueError("Duplicate source geographic IDs")
    if set(geometry.UNIQUE_ID) != set(seed.UNIQUE_ID) or set(geometry.UNIQUE_ID) != set(aggregate.PRECINCTID):
        raise ValueError("Source geography, seed, and block aggregates differ")
    candidate = geometry.merge(seed, on="UNIQUE_ID", validate="one_to_one").merge(
        aggregate, left_on="UNIQUE_ID", right_on="PRECINCTID", validate="one_to_one"
    ).reset_index(drop=True)
    if len(candidate) != 9712 or candidate.CONG_DIST.nunique() != 38:
        raise ValueError("Unexpected candidate dimensions")
    if candidate[METRICS].isna().any().any() or (candidate[METRICS] < 0).any().any():
        raise ValueError("Missing or negative candidate data")
    for metric in METRICS:
        if int(candidate[metric].sum()) != int(blocks[metric].sum()):
            raise ValueError("Candidate statewide total mismatch")
    if int(candidate.BLOCK_COUNT.sum()) != len(blocks):
        raise ValueError("Candidate lost blocks")
    report = inspect_geometry(candidate, "CONG_DIST")
    report["repairs"] = repairs
    report["totals"] = {column: int(candidate[column].sum()) for column in METRICS}
    pops = candidate.groupby("CONG_DIST").TOTPOP.sum()
    report["seed_max_abs_population_deviation"] = float(abs(pops / pops.mean() - 1).max())
    report["planc2333_split_precincts"] = int((candidate.PLANC2333_DISTRICTS > 1).sum())
    report["planc2333_scoring"] = "Separate official block assignment; never assigned to a whole split precinct"
    report["inputs"] = [{"path": str(path), "sha256": sha256(path)} for path in (source, args.block_master)]
    args.output_dir.mkdir(parents=True, exist_ok=False)
    candidate.to_file(args.output_dir / "tx_candidate.gpkg", layer="precincts", driver="GPKG")
    with (args.output_dir / "candidate_audit.json").open("x") as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({key: report[key] for key in (
        "features", "invalid", "overlap_pairs", "max_pairwise_overlap_area_m2",
        "graph_components", "district_components", "seed_max_abs_population_deviation",
        "planc2333_split_precincts", "totals",
    )}, indent=2))


if __name__ == "__main__":
    main()
