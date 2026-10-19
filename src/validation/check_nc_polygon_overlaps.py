"""Identify overlapping North Carolina GerryChain geographic units."""

import csv
from pathlib import Path

import geopandas as gpd

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "data/processed/nc_precincts_validated.gpkg"
OUTPUT = ROOT / "data/processed/nc_geometry_overlaps.csv"

units = gpd.read_file(
    SOURCE,
    layer="precincts",
    columns=["UNIT_ID", "CONG_DIST"],
).reset_index(drop=True)

if len(units) != 2680:
    raise ValueError("Unexpected geographic unit count")

if units.crs is None or units.crs.to_epsg() != 2264:
    raise ValueError("Unexpected coordinate system")

if not units.geometry.is_valid.all():
    raise ValueError("Invalid geographic unit geometry")

index = units.sindex
overlaps = []

print("Checking polygon intersections...")

for i, geometry in enumerate(units.geometry):
    for j in index.query(geometry, predicate="intersects"):
        j = int(j)

        if j <= i:
            continue

        other = units.geometry.iloc[j]
        overlap_area = geometry.intersection(other).area

        if overlap_area <= 0:
            continue

        smaller_area = min(geometry.area, other.area)

        overlaps.append({
            "unit_a": units.at[i, "UNIT_ID"],
            "unit_b": units.at[j, "UNIT_ID"],
            "district_a": str(units.at[i, "CONG_DIST"]),
            "district_b": str(units.at[j, "CONG_DIST"]),
            "overlap_sqft": overlap_area,
            "smaller_unit_overlap_pct": (
                100 * overlap_area / smaller_area
            ),
        })

overlaps.sort(
    key=lambda row: row["overlap_sqft"],
    reverse=True,
)

material = [
    row for row in overlaps
    if row["overlap_sqft"] >= 1
]

cross_district = [
    row for row in material
    if row["district_a"] != row["district_b"]
]

print(f"Total positive-area overlaps: {len(overlaps)}")
print(f"Overlaps >= 1 sq ft: {len(material)}")
print(f"Cross-district overlaps >= 1 sq ft: {len(cross_district)}")

print("\nLargest 20 overlaps:")

for row in overlaps[:20]:
    print(
        f"{row['unit_a']} [{row['district_a']}]"
        f"  vs  {row['unit_b']} [{row['district_b']}]"
    )
    print(
        f"  Area: {row['overlap_sqft']:,.2f} sq ft"
        f" | Smaller unit: "
        f"{row['smaller_unit_overlap_pct']:.4f}%"
    )

with OUTPUT.open("w", newline="", encoding="utf-8") as file:
    writer = csv.DictWriter(
        file,
        fieldnames=[
            "unit_a", "unit_b",
            "district_a", "district_b",
            "overlap_sqft", "smaller_unit_overlap_pct"
        ],
    )
    writer.writeheader()
    writer.writerows(overlaps)

print(f"\nFull overlap report: {OUTPUT}")
print("Overlap audit complete")

