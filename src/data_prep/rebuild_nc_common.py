"""Reconstruct an NC common-geography candidate without repairing source polygons.

The Wake union and official district intersections are explicit construction
operations. Any uncovered slivers and overlaps remain measured, not reassigned.
"""

import argparse
import json
from pathlib import Path
import re
import sys

import geopandas as gpd
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.validation.audit_rdh_geometry import inspect_geometry
from src.validation.audit_rdh_sources import sha256

METRICS = ["TOTPOP", "G24PREDHAR", "G24PRERTRU"]
WAKE = "WAKE-:-01-07"
EXTRA = "WAKE-:-01-07A"
COMBINED = "WAKE-:-01-07 & WAKE-:-01-07A"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--block-master", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    for path in (args.source_root, args.block_master, args.output_dir):
        path.resolve().relative_to(ROOT)
    if args.output_dir.exists():
        raise FileExistsError("Candidate output directory already exists")
    source = (args.source_root / "north_carolina").resolve()
    blocks = pd.read_csv(args.block_master, dtype={"GEOID20": str, "PRECINCTID": str})
    if len(blocks) != 236638 or not blocks.GEOID20.is_unique:
        raise ValueError("Unexpected or duplicate block coverage")
    if blocks.isna().any().any() or (blocks[METRICS] < 0).any().any():
        raise ValueError("Missing or negative block data")
    blocks["PRECINCT_KEY"] = blocks.PRECINCTID.replace({COMBINED: WAKE})
    groups = blocks.groupby(["PRECINCT_KEY", "DISTRICT_2023", "DISTRICT_2025"])
    aggregates = groups.agg(
        BLOCK_COUNT=("GEOID20", "size"), TOTPOP=("TOTPOP", "sum"),
        G24PREDHAR=("G24PREDHAR", "sum"), G24PRERTRU=("G24PRERTRU", "sum"),
    ).reset_index()
    precinct_zip = source / "nc_2024_gen_prec.zip"
    stem = "nc_2024_gen_cong_prec"
    features = gpd.read_file(f"/vsizip/{precinct_zip}/{stem}/{stem}.shp", columns=["UNIQUE_ID"])
    if len(features) != 2678 or not features.UNIQUE_ID.is_unique:
        raise ValueError("Unexpected source congressional precincts")
    if not features.geometry.is_valid.all() or features.geometry.is_empty.any():
        raise ValueError("Invalid source congressional precinct geometry")
    plans = {}
    plan_paths = {}
    members = {2023: "SL 2023-145 Congress - Shapefile/SL 2023-145.shp",
               2025: "NCGA_CCM-2 - Shapefile/CCM-2.shp"}
    for year in (2023, 2025):
        path = source / f"nc_cong_adopted_{year}.zip"
        plan_paths[year] = path
        frame = gpd.read_file(f"/vsizip/{path}/{members[year]}").to_crs(features.crs)
        frame["DISTRICT"] = frame.DISTRICT.astype(int)
        if len(frame) != 14 or set(frame.DISTRICT) != set(range(1, 15)):
            raise ValueError("Unexpected official districts")
        if not frame.geometry.is_valid.all():
            raise ValueError("Invalid official district boundaries")
        plans[year] = frame.set_index("DISTRICT").geometry.to_dict()
    source_shapes = features.set_index("UNIQUE_ID").geometry
    wake_union = source_shapes[WAKE].union(source_shapes[EXTRA])
    if not wake_union.is_valid:
        raise ValueError("Wake union is invalid")
    by_precinct = {key: frame for key, frame in aggregates.groupby("PRECINCT_KEY")}
    suffix = re.compile(r"(.+)-\(CON-(\d{2})\)$")
    records, coverage, keys = [], [], set()
    units_per_metre = float(features.crs.axis_info[0].unit_conversion_factor)
    extra_splits = set()
    for feature in features.itertuples(index=False):
        name = feature.UNIQUE_ID
        if name == EXTRA:
            continue
        found = suffix.fullmatch(name)
        base = found.group(1) if found else name
        frame = by_precinct.get(base)
        if frame is None:
            raise ValueError(f"No block aggregates for source unit {name}")
        original = wake_union if name == WAKE else feature.geometry
        districts23 = sorted(frame.DISTRICT_2023.unique())
        if found:
            districts23 = [int(found.group(2))]
        elif len(districts23) > 1:
            extra_splits.add(base)
        pieces23 = []
        for district23 in districts23:
            piece23 = original
            if not found and len(districts23) > 1:
                piece23 = original.intersection(plans[2023][district23])
            pieces23.append(piece23)
            rows = frame.loc[frame.DISTRICT_2023 == district23]
            if rows.empty:
                raise ValueError("Source suffix does not match official block assignment")
            pieces25 = []
            for row in rows.itertuples(index=False):
                key = (base, district23, int(row.DISTRICT_2025))
                if key in keys:
                    raise ValueError("Duplicate candidate common-geography key")
                keys.add(key)
                piece = piece23 if len(rows) == 1 else piece23.intersection(plans[2025][row.DISTRICT_2025])
                if piece.is_empty or not piece.is_valid or piece.geom_type not in ("Polygon", "MultiPolygon"):
                    raise ValueError(f"Invalid candidate geometry at {key}")
                pieces25.append(piece)
                unit_id = f"{base}|{district23:02d}"
                if len(rows) > 1:
                    unit_id += f"|25-{row.DISTRICT_2025:02d}"
                records.append({
                    "UNIT_ID": unit_id, "UNIQUE_ID": unit_id, "PRECINCT_KEY": base,
                    "CONG_DIST": f"{district23:02d}", "CONG_DIST_2025": f"{row.DISTRICT_2025:02d}",
                    "BLOCK_COUNT": int(row.BLOCK_COUNT),
                    **{column: int(getattr(row, column)) for column in METRICS}, "geometry": piece,
                })
            if len(rows) > 1:
                union = gpd.GeoSeries(pieces25, crs=features.crs).union_all()
                coverage.append({"unit": f"{base}|{district23:02d}", "operation": "2025 official intersections",
                                 "uncovered_m2": piece23.difference(union).area * units_per_metre ** 2,
                                 "outside_m2": union.difference(piece23).area * units_per_metre ** 2})
        if not found and len(districts23) > 1:
            union = gpd.GeoSeries(pieces23, crs=features.crs).union_all()
            coverage.append({"unit": base, "operation": "2023 official intersections",
                             "uncovered_m2": original.difference(union).area * units_per_metre ** 2,
                             "outside_m2": union.difference(original).area * units_per_metre ** 2})
    candidate = gpd.GeoDataFrame(records, crs=features.crs).reset_index(drop=True)
    expected_keys = set(aggregates[["PRECINCT_KEY", "DISTRICT_2023", "DISTRICT_2025"]].itertuples(index=False, name=None))
    if keys != expected_keys or len(candidate) != 2681 or not candidate.UNIT_ID.is_unique:
        raise ValueError("Candidate and block aggregate coverage mismatch")
    if int(candidate.BLOCK_COUNT.sum()) != len(blocks):
        raise ValueError("Block coverage was not preserved")
    for column in METRICS:
        if int(candidate[column].sum()) != int(blocks[column].sum()):
            raise ValueError("Statewide total changed")
    for year, column in ((2023, "CONG_DIST"), (2025, "CONG_DIST_2025")):
        actual = candidate.groupby(column)[METRICS].sum()
        actual.index = actual.index.astype(int)
        expected = blocks.groupby(f"DISTRICT_{year}")[METRICS].sum()
        if not actual.sort_index().equals(expected.sort_index()):
            raise ValueError(f"{year} district totals differ from official block aggregation")
    report = inspect_geometry(candidate, "CONG_DIST")
    report["district_components_2023"] = report.pop("district_components")
    second = inspect_geometry(candidate, "CONG_DIST_2025")
    report["district_components_2025"] = second["district_components"]
    report["construction_coverage"] = coverage
    report["extra_2023_splits"] = sorted(extra_splits)
    report["wake_operation"] = "Union of both source precinct polygons; combined block ID mapped to that union"
    report["geometry_repair"] = "none; no slivers assigned and no snapping"
    report["inputs"] = [{"path": str(path), "sha256": sha256(path)}
                        for path in [args.block_master, precinct_zip, *plan_paths.values()]]
    report["totals"] = {column: int(candidate[column].sum()) for column in METRICS}
    report["onslow"] = candidate.loc[candidate.PRECINCT_KEY == "ONSLOW-:-SW19",
        ["UNIT_ID", "CONG_DIST", "CONG_DIST_2025", "BLOCK_COUNT", *METRICS]].to_dict("records")
    args.output_dir.mkdir(parents=True, exist_ok=False)
    candidate.to_file(args.output_dir / "nc_common_candidate.gpkg", layer="precincts", driver="GPKG")
    with (args.output_dir / "candidate_audit.json").open("x") as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({key:report[key] for key in (
        "features", "overlap_pairs", "max_pairwise_overlap_area_m2", "graph_components",
        "district_components_2023", "district_components_2025", "construction_coverage", "onslow",
    )}, indent=2))


if __name__ == "__main__":
    main()
