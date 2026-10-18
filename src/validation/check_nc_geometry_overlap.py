"""Verify NC precinct intersections with the 2023 congressional map."""

from pathlib import Path
import geopandas as gpd

ROOT = Path(__file__).resolve().parents[2]

precinct_path = (
    ROOT / "data/raw/nc/precincts/nc_2024_gen_all_prec"
    / "nc_2024_gen_all_prec.shp"
)

plan_path = (
    ROOT / "data/raw/nc/plan_2023"
    / "SL 2023-145 Congress - Shapefile"
    / "SL 2023-145.shp"
)

precincts = gpd.read_file(precinct_path, columns=["UNIQUE_ID"])
plan = gpd.read_file(plan_path).to_crs(precincts.crs)

if len(precincts) != 2658 or len(plan) != 14:
    raise ValueError("Unexpected geographic feature count")

if not precincts.geometry.is_valid.all() or not plan.geometry.is_valid.all():
    raise ValueError("Invalid polygon found")

for name in (
    "FORSYTH-:-508",
    "FORSYTH-:-605",
    "GUILFORD-:-G65",
):
    matched = precincts.loc[precincts["UNIQUE_ID"] == name]

    if len(matched) != 1:
        raise ValueError(f"Expected one polygon: {name}")

    polygon = matched.geometry.iloc[0]
    total = 0.0

    print(f"\n{name}")

    for row in plan.itertuples():
        area = polygon.intersection(row.geometry).area

        if area > 0.01:
            total += area
            share = 100 * area / polygon.area

            print(f"  District {row.DISTRICT}: {share:.4f}%")

    if abs(total - polygon.area) / polygon.area > 1e-5:
        raise ValueError(f"Incomplete district coverage: {name}")

wake = precincts.set_index("UNIQUE_ID").geometry

first = wake.loc["WAKE-:-01-07"]
second = wake.loc["WAKE-:-01-07A"]

print("\nWake precincts share boundary:", first.touches(second))
print("Wake union geometry:", first.union(second).geom_type)
print("Geographic intersection validation passed")
