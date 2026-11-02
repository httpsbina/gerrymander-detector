"""Inspect source polygons without repairing geometry or changing adjacency."""

import argparse
import json
from pathlib import Path

import geopandas as gpd
import networkx as nx
import shapely
from shapely.errors import GEOSException

ROOT = Path(__file__).resolve().parents[2]


def inspect_geometry(frame, assignment=None):
    frame = frame.reset_index(drop=True)
    if frame.crs is None or not frame.crs.is_projected:
        raise ValueError("A projected source CRS is required for this audit")
    units = float(frame.crs.axis_info[0].unit_conversion_factor)
    if units != float(frame.crs.axis_info[1].unit_conversion_factor):
        raise ValueError("Inconsistent projected axis units")
    ids = frame.UNIQUE_ID.astype(str).tolist()
    geometries = frame.geometry.to_numpy()
    valid = frame.geometry.is_valid.to_numpy()
    report = {
        "features": len(frame), "unique_ids": len(set(ids)),
        "missing_ids": int(frame.UNIQUE_ID.isna().sum()),
        "crs": str(frame.crs), "linear_unit_metres": units,
        "invalid": [{"id": ids[i], "reason": shapely.is_valid_reason(geom)}
                    for i, geom in enumerate(geometries) if not valid[i]],
        "empty": int(frame.geometry.is_empty.sum()),
        "missing_geometry": int(frame.geometry.isna().sum()),
        "overlaps": [], "intersection_errors": [],
        "adjacency_definition": "Positive shared source-polygon boundary length; no repair or added edges",
    }
    graph = nx.Graph()
    graph.add_nodes_from(range(len(frame)))
    pairs = frame.sindex.query(frame.geometry, predicate="intersects")
    for left, right in zip(*pairs):
        if left >= right:
            continue
        try:
            intersection = geometries[left].intersection(geometries[right])
            area = float(intersection.area) * units ** 2
            if area > 0:
                report["overlaps"].append({"left": ids[left], "right": ids[right], "area_m2": area})
            boundary = geometries[left].boundary.intersection(geometries[right].boundary)
            if boundary.length > 0:
                graph.add_edge(int(left), int(right))
        except GEOSException:
            report["intersection_errors"].append({"left": ids[left], "right": ids[right]})
    report["overlaps"].sort(key=lambda row: row["area_m2"], reverse=True)
    report["overlap_pairs"] = len(report["overlaps"])
    report["sum_pairwise_overlap_area_m2"] = sum(row["area_m2"] for row in report["overlaps"])
    report["max_pairwise_overlap_area_m2"] = max((row["area_m2"] for row in report["overlaps"]), default=0)
    report["graph_nodes"] = len(graph)
    report["graph_edges"] = graph.number_of_edges()
    report["graph_components"] = nx.number_connected_components(graph)
    report["graph_status"] = (
        "unvalidated; invalid geometry or intersection errors"
        if report["invalid"] or report["intersection_errors"] or report["missing_geometry"]
        else "computed on valid source polygons; overlaps still require review"
    )
    report["isolates"] = [ids[i] for i in nx.isolates(graph)]
    if assignment is not None:
        report["district_components"] = {
            str(district): nx.number_connected_components(graph.subgraph(
                frame.index[frame[assignment] == district].tolist()
            )) for district in sorted(frame[assignment].unique())
        }
    else:
        report["district_components"] = "unavailable; source has no validated starting assignment"
    report["research_ready"] = False
    report["review_required"] = bool(
        report["invalid"] or report["empty"] or report["missing_geometry"]
        or report["missing_ids"] or report["unique_ids"] != len(frame)
        or report["overlaps"] or report["intersection_errors"]
        or report["graph_components"] != 1
        or (isinstance(report["district_components"], dict)
            and any(value != 1 for value in report["district_components"].values()))
    )
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", choices=("texas", "north_carolina"), required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    for path in (args.source_root, args.output_dir):
        path.resolve().relative_to(ROOT)
    if args.output_dir.exists():
        raise FileExistsError("Refusing existing geometry audit directory")
    prefix, unit = ("tx", "tx_vtd") if args.state == "texas" else ("nc", "prec")
    source = (args.source_root / args.state / f"{prefix}_2024_gen_{unit}.zip").resolve()
    reports = {"state": args.state, "source": str(source), "research_ready": False, "layers": {}}
    for category in ("all", "cong"):
        stem = f"{prefix}_2024_gen_{category}_{unit}"
        frame = gpd.read_file(f"/vsizip/{source}/{stem}/{stem}.shp")
        assignment = "CONG_DIST" if "CONG_DIST" in frame else None
        report = inspect_geometry(frame, assignment)
        reports["layers"][category] = report
        print(args.state, category, {key: report[key] for key in (
            "features", "unique_ids", "overlap_pairs", "max_pairwise_overlap_area_m2",
            "graph_components", "district_components",
        )}, "invalid:", len(report["invalid"]), flush=True)
    args.output_dir.mkdir(parents=True, exist_ok=False)
    with (args.output_dir / "geometry_audit.json").open("x") as stream:
        json.dump(reports, stream, indent=2, allow_nan=False)
        stream.write("\n")
    return 1 if any(report["review_required"] for report in reports["layers"].values()) else 0


if __name__ == "__main__":
    raise SystemExit(main())
