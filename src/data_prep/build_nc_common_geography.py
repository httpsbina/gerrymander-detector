"""Build NC geography compatible with both enacted congressional plans."""

from pathlib import Path

import geopandas as gpd
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PROCESSED = ROOT / "data/processed"

SOURCE = PROCESSED / "nc_precincts_validated.gpkg"
BLOCKS = PROCESSED / "nc_blocks_master.csv"
REFERENCE = PROCESSED / "nc_plan_comparison.csv"

PLAN = (
    ROOT / "data/raw/nc/plan_2025"
    / "NCGA_CCM-2 - Shapefile/CCM-2.shp"
)

OUTPUT = PROCESSED / "nc_precincts_common_2023_2025.gpkg"

SPLIT_UNIT = "ONSLOW-:-SW19|03"
METRICS = ["TOTPOP", "G24PREDHAR", "G24PRERTRU"]

EXPECTED_TOTALS = (10_439_388, 2_713_609, 2_896_942)

print("Reading existing validated NC geography...")

units = gpd.read_file(SOURCE, layer="precincts")

if len(units) != 2680 or not units.UNIT_ID.is_unique:
    raise ValueError("Unexpected original geographic units")

if units.crs is None or not units.geometry.is_valid.all():
    raise ValueError("Invalid original geography")

print("Reading Census block assignments...")

blocks = pd.read_csv(
    BLOCKS,
    usecols=[
        "GEOID20", "PRECINCTID",
        "DISTRICT_2023", "DISTRICT_2025",
        *METRICS
    ],
    dtype={"GEOID20": str, "PRECINCTID": str}
)

if len(blocks) != 236638 or not blocks.GEOID20.is_unique:
    raise ValueError("Invalid Census block coverage")

if blocks.isna().any().any():
    raise ValueError("Missing Census block data")

blocks["PRECINCT_KEY"] = blocks.PRECINCTID.replace({
    "WAKE-:-01-07 & WAKE-:-01-07A": "WAKE-:-01-07"
})

blocks["UNIT_ID"] = (
    blocks.PRECINCT_KEY + "|" +
    blocks.DISTRICT_2023.astype(str).str.zfill(2)
)

aggregates = (
    blocks.groupby(
        ["UNIT_ID", "DISTRICT_2025"],
        as_index=False
    )
    .agg(
        BLOCK_COUNT=("GEOID20", "size"),
        TOTPOP=("TOTPOP", "sum"),
        G24PREDHAR=("G24PREDHAR", "sum"),
        G24PRERTRU=("G24PRERTRU", "sum")
    )
)

groups = {
    key: group
    for key, group in aggregates.groupby("UNIT_ID")
}

if set(groups) != set(units.UNIT_ID):
    raise ValueError("Block and geographic unit IDs do not match")

mixed = [
    key for key, group in groups.items()
    if len(group) > 1
]

if mixed != [SPLIT_UNIT]:
    raise ValueError(f"Unexpected split units: {mixed}")

print("Reading official 2025 congressional boundaries...")

plan = gpd.read_file(PLAN)

if "DISTRICT" not in plan.columns or plan.crs is None:
    raise ValueError("Invalid 2025 congressional shapefile")

plan["DISTRICT"] = pd.to_numeric(
    plan.DISTRICT
).astype(int)

if (
    len(plan) != 14
    or set(plan.DISTRICT) != set(range(1, 15))
    or not plan.geometry.is_valid.all()
):
    raise ValueError("Unexpected 2025 congressional boundaries")

plan = plan.to_crs(units.crs)

original = units.loc[
    units.UNIT_ID == SPLIT_UNIT, "geometry"
].iloc[0]

district1 = plan.loc[
    plan.DISTRICT == 1, "geometry"
].iloc[0]

district3 = plan.loc[
    plan.DISTRICT == 3, "geometry"
].iloc[0]

piece1 = original.intersection(district1)
official_piece3 = original.intersection(district3)

uncovered = original.difference(
    piece1.union(official_piece3)
).area

overlap = piece1.intersection(official_piece3).area

if uncovered > 1 or overlap > 1:
    raise ValueError(
        f"Boundary disagreement: uncovered={uncovered}, "
        f"overlap={overlap}"
    )

# Assign the negligible uncovered numerical sliver to District 3,
# preserving complete coverage of the original 2023 geographic unit.
piece3 = original.difference(piece1)

if piece3.symmetric_difference(official_piece3).area > 1:
    raise ValueError("District 3 geometry differs from official boundary")

pieces = {1: piece1, 3: piece3}

for district, geometry in pieces.items():
    if (
        geometry.is_empty
        or not geometry.is_valid
        or geometry.area <= 0
        or geometry.geom_type not in ("Polygon", "MultiPolygon")
    ):
        raise ValueError(f"Invalid split geometry for {district}")

print(f"Uncovered area before correction: {uncovered:.9f}")
print(f"Area overlap before correction: {overlap:.9f}")

print("Building common geographic units...")

records = []

for original_row in units.itertuples(index=False):
    base = original_row._asdict()
    key = base["UNIT_ID"]
    group = groups[key]

    for part in group.itertuples(index=False):
        record = base.copy()

        record["DISTRICT_2023"] = int(base["CONG_DIST"])
        record["DISTRICT_2025"] = int(part.DISTRICT_2025)
        record["CONG_DIST_2025"] = (
            str(part.DISTRICT_2025).zfill(2)
        )

        for column in ["BLOCK_COUNT", *METRICS]:
            record[column] = int(getattr(part, column))

        if key == SPLIT_UNIT:
            district = int(part.DISTRICT_2025)
            record["UNIT_ID"] = (
                f"{key}|25-{district:02d}"
            )
            record["geometry"] = pieces[district]

        records.append(record)

common = gpd.GeoDataFrame(
    records, geometry="geometry", crs=units.crs
)

if len(common) != 2681 or not common.UNIT_ID.is_unique:
    raise ValueError("Common geography unit count mismatch")

if common.geometry.is_empty.any():
    raise ValueError("Empty common geography")

if not common.geometry.is_valid.all():
    raise ValueError("Invalid common geography")

if int(common.BLOCK_COUNT.sum()) != 236638:
    raise ValueError("Lost Census blocks")

if tuple(int(common[x].sum()) for x in METRICS) != EXPECTED_TOTALS:
    raise ValueError("Statewide totals changed")

reference = pd.read_csv(REFERENCE)

for year in (2023, 2025):
    expected = (
        reference[reference.plan_year == year]
        .set_index("district")
        .sort_index()
    )

    actual = (
        common.groupby(f"DISTRICT_{year}")[METRICS]
        .sum()
        .sort_index()
    )

    if list(actual.index) != list(range(1, 15)):
        raise ValueError(f"{year} district coverage mismatch")

    for actual_col, expected_col in [
        ("TOTPOP", "population"),
        ("G24PREDHAR", "harris_votes"),
        ("G24PRERTRU", "trump_votes")
    ]:
        if not actual[actual_col].equals(
            expected[expected_col].astype("int64")
        ):
            raise ValueError(
                f"{year} district totals differ: {actual_col}"
            )

    print(f"{year}: all 14 district totals match block data")

if common.loc[
    common.UNIT_ID.str.startswith(SPLIT_UNIT + "|25-"),
    "TOTPOP"
].sum() != 7450:
    raise ValueError("Onslow split population mismatch")

OUTPUT.parent.mkdir(parents=True, exist_ok=True)

common.to_file(
    OUTPUT, layer="precincts", driver="GPKG"
)

print("\nNC COMMON GEOGRAPHY COMPLETE")
print(f"Geographic units: {len(common):,}")
print(f"Population: {int(common.TOTPOP.sum()):,}")
print(f"Harris votes: {int(common.G24PREDHAR.sum()):,}")
print(f"Trump votes: {int(common.G24PRERTRU.sum()):,}")
print("\nOnslow split units:")

print(
    common.loc[
        common.UNIT_ID.str.startswith(SPLIT_UNIT + "|25-"),
        [
            "UNIT_ID", "BLOCK_COUNT", "TOTPOP",
            "G24PREDHAR", "G24PRERTRU",
            "CONG_DIST", "CONG_DIST_2025"
        ]
    ].to_string(index=False)
)

print(f"\nSaved: {OUTPUT}")
print("Common geography totals validated")
print("Graph connectivity and contiguity still need testing")
