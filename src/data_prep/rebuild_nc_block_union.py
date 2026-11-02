"""Build the approved new-source NC baseline candidate from Census blocks.

All block membership comes from the audited master. No polygon repair, snapping,
centroid reassignment, population imputation, or production replacement occurs.
"""

import argparse
import json
from pathlib import Path
import sys

import geopandas as gpd
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.validation.audit_rdh_geometry import inspect_geometry
from src.validation.audit_rdh_sources import sha256

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
        raise FileExistsError("Refusing existing block-union candidate directory")
    archive = (args.source_root / "north_carolina/nc_pl2020_b.zip").resolve()
    shapes = gpd.read_file(f"/vsizip/{archive}/nc_pl2020_p1_b.shp", columns=["GEOID20"])
    blocks = pd.read_csv(args.block_master, dtype={"GEOID20": str, "PRECINCTID": str})
    if not shapes.GEOID20.is_unique or not blocks.GEOID20.is_unique:
        raise ValueError("Duplicate block IDs")
    if len(shapes) != 236638 or set(shapes.GEOID20) != set(blocks.GEOID20):
        raise ValueError("Census and master block coverage differ")
    if not shapes.geometry.is_valid.all() or shapes.geometry.is_empty.any():
        raise ValueError("Invalid or empty source block geometry; no repair permitted")
    blocks["PRECINCT_KEY"] = blocks.PRECINCTID.replace({"WAKE-:-01-07 & WAKE-:-01-07A": "WAKE-:-01-07"})
    joined = shapes.merge(blocks, on="GEOID20", validate="one_to_one")
    print('Unioning all 236,638 Census blocks, including zero-population blocks...', flush=True)
    keys = ["PRECINCT_KEY", "DISTRICT_2023", "DISTRICT_2025"]
    candidate = joined.dissolve(by=keys, as_index=False, aggfunc={
        "GEOID20": "size", **{column: "sum" for column in METRICS},
    }).rename(columns={"GEOID20": "BLOCK_COUNT"}).to_crs("EPSG:2264")
    candidate["CONG_DIST"] = candidate.DISTRICT_2023.astype(str).str.zfill(2)
    candidate["CONG_DIST_2025"] = candidate.DISTRICT_2025.astype(str).str.zfill(2)
    candidate["UNIT_ID"] = candidate.PRECINCT_KEY + "|" + candidate.CONG_DIST
    mixed = candidate.groupby("UNIT_ID").DISTRICT_2025.transform("size") > 1
    candidate.loc[mixed, "UNIT_ID"] += "|25-" + candidate.loc[mixed, "CONG_DIST_2025"]
    candidate["UNIQUE_ID"] = candidate.UNIT_ID
    if len(candidate) != 2681 or not candidate.UNIT_ID.is_unique:
        raise ValueError("Unexpected block-union geographic units")
    if int(candidate.BLOCK_COUNT.sum()) != 236638:
        raise ValueError("Lost Census blocks")
    for metric in METRICS:
        if int(candidate[metric].sum()) != int(blocks[metric].sum()):
            raise ValueError("Statewide totals changed")
    for year in (2023, 2025):
        column = f"DISTRICT_{year}"
        if not candidate.groupby(column)[METRICS].sum().equals(blocks.groupby(column)[METRICS].sum()):
            raise ValueError("Official district block totals changed")
    report = inspect_geometry(candidate, "CONG_DIST")
    report["district_components_2023"] = report.pop("district_components")
    report["district_components_2025"] = inspect_geometry(candidate, "CONG_DIST_2025")["district_components"]
    report["construction"] = "Union of every official Census block according to audited precinct/2023/2025 block membership"
    report["production_replacement"] = False
    report["geometry_repairs"] = "none"
    report["block_membership_limitation"] = "Precinct membership originates in RDH's modeled block assignment, including documented nearest-precinct fallbacks"
    report["totals"] = {column: int(candidate[column].sum()) for column in METRICS}
    report["inputs"] = [{"path": str(path), "sha256": sha256(path)} for path in (archive, args.block_master)]
    args.output_dir.mkdir(parents=True, exist_ok=False)
    candidate.to_file(args.output_dir / "nc_block_union_candidate.gpkg", layer="precincts", driver="GPKG")
    with (args.output_dir / "candidate_audit.json").open("x") as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({key:report[key] for key in (
        "features", "overlap_pairs", "graph_components", "graph_edges", "isolates",
        "district_components_2023", "district_components_2025", "invalid", "totals",
    )}, indent=2))


if __name__ == "__main__":
    main()
