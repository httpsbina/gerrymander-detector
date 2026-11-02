"""Measure NC graph changes under explicit coordinate-precision scenarios.

This experiment never writes rounded geometry or selects a production graph.
"""

import argparse
import json
from pathlib import Path
import sys

import geopandas as gpd
import shapely

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.validation.audit_adjacency_sensitivity import compare


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    for path in (args.dataset, args.output):
        path.resolve().relative_to(ROOT)
    if args.output.exists():
        raise FileExistsError("Refusing existing precision sensitivity report")
    source = gpd.read_file(args.dataset, layer="precincts")
    if source.crs.to_epsg() != 2264:
        raise ValueError("This precision experiment is defined in NC's EPSG:2264 US survey feet")
    metres = float(source.crs.axis_info[0].unit_conversion_factor)
    report = {"research_ready": False, "production_geometry_changed": False, "scenarios": []}
    for grid in (0, 1e-8, 1e-6, 1e-4, 0.01):
        candidate = source.copy()
        if grid:
            candidate.geometry = shapely.set_precision(source.geometry.to_numpy(), grid)
        changed = int((candidate.geometry.to_wkb() != source.geometry.to_wkb()).sum())
        scenario = {"grid_us_survey_feet": grid, "changed_wkb_records": changed,
                    "empty_records": int(candidate.geometry.is_empty.sum()),
                    "invalid_records": int((~candidate.geometry.is_valid).sum())}
        if not scenario["empty_records"] and not scenario["invalid_records"]:
            scenario["sum_symmetric_difference_area_m2"] = float(
                shapely.area(shapely.symmetric_difference(source.geometry.to_numpy(), candidate.geometry.to_numpy())).sum()
            ) * metres ** 2
            scenario["adjacency"] = compare(candidate)
            print(grid, "sampler edges", scenario["adjacency"]["sampler_edges"],
                  "boundary edges", scenario["adjacency"]["boundary_edges"], flush=True)
        else:
            scenario["adjacency"] = "unavailable; empty or invalid scenario geometry"
        report["scenarios"].append(scenario)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write("\n")


if __name__ == "__main__":
    main()
