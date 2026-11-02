"""Audit adopted district polygons separately from block-based election scoring."""

import argparse
import json
from pathlib import Path
import sys
from zipfile import ZipFile

import geopandas as gpd
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.chain.checkpoint_integrity import file_sha256
from src.validation.audit_rdh_geometry import inspect_geometry


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--audit-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    for path in (args.source_root, args.audit_root, args.output_dir):
        path.resolve().relative_to(ROOT)
    if args.output_dir.exists():
        raise FileExistsError("Refusing existing adopted-plan audit directory")
    reports = {}
    for state, short, year, count in (("texas", "tx", 2025, 38),
                                      ("north_carolina", "nc", 2023, 14),
                                      ("north_carolina", "nc", 2025, 14)):
        archive = (args.source_root / state / f"{short}_cong_adopted_{year}.zip").resolve()
        with ZipFile(archive) as stream:
            members = [name for name in stream.namelist() if name.endswith(".shp")]
        if len(members) != 1:
            raise ValueError("Ambiguous adopted district layer")
        frame = gpd.read_file(f"/vsizip/{archive}/{members[0]}")
        column = "District" if state == "texas" else "DISTRICT"
        frame["UNIQUE_ID"] = frame[column].astype(int).astype(str)
        if len(frame) != count or set(frame.UNIQUE_ID) != set(map(str, range(1, count + 1))):
            raise ValueError("District IDs do not match the official plan")
        report = inspect_geometry(frame)
        report["physical_polygon_components"] = {
            row.UNIQUE_ID: (len(row.geometry.geoms) if row.geometry.geom_type == "MultiPolygon" else 1)
            for row in frame.itertuples()}
        report["all_districts_single_valid_polygon"] = bool(
            frame.geometry.is_valid.all() and not frame.geometry.is_empty.any()
            and (frame.geometry.geom_type == "Polygon").all())
        report["interpretation"] = "Physical district-polygon connectedness; not a block-graph equivalence proof or a full legal-compliance finding"
        report["source"] = {"path": str(archive), "sha256": file_sha256(archive), "member": members[0]}
        if state == "north_carolina":
            master = args.audit_root / "nc_block_audit/blocks_master.csv"
            blocks = pd.read_csv(master, usecols=["TOTPOP", f"DISTRICT_{year}"])
            expected = blocks.groupby(f"DISTRICT_{year}").TOTPOP.sum()
            actual = frame.set_index(frame[column].astype(int)).PL20AA_TOT
            report["district_population_matches_block_master"] = bool(actual.sort_index().equals(expected.sort_index()))
            if not report["district_population_matches_block_master"]:
                raise ValueError("Source district polygon and official block population totals differ")
            report["block_master_sha256"] = file_sha256(master)
        reports[f"{short}_{year}"] = report
    args.output_dir.mkdir(parents=True, exist_ok=False)
    with (args.output_dir / "adopted_plan_geometry.json").open("x") as stream:
        json.dump({"research_ready": False, "plans": reports}, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({key: {name: value[name] for name in (
        "all_districts_single_valid_polygon", "overlap_pairs", "max_pairwise_overlap_area_m2")}
        for key, value in reports.items()}, indent=2))
    return int(any(value["review_required"] or not value["all_districts_single_valid_polygon"] for value in reports.values()))


if __name__ == "__main__":
    sys.exit(main())
