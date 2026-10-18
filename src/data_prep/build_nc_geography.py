"""Build the 2023 NC congressional seed geography for GerryChain."""

import re
from pathlib import Path

import geopandas as gpd
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data/raw/nc"
PROCESSED = ROOT / "data/processed"

BLOCKS = PROCESSED / "nc_blocks_master.csv"
COMPARISON = PROCESSED / "nc_plan_comparison.csv"
SHAPE = (
    RAW / "precincts/nc_2024_gen_cong_prec"
    / "nc_2024_gen_cong_prec.shp"
)
PLAN = (
    RAW / "plan_2023/SL 2023-145 Congress - Shapefile"
    / "SL 2023-145.shp"
)
OUTPUT = PROCESSED / "nc_precincts_validated.gpkg"

EXPECTED_BLOCKS = 236_638
EXPECTED_UNITS = 2_680
EXPECTED_TOTALS = (10_439_388, 2_713_609, 2_896_942)

EXTRA_SPLITS = {
    "FORSYTH-:-508",
    "FORSYTH-:-605",
    "GUILFORD-:-G65",
}

WAKE_ORIGINAL = "WAKE-:-01-07"
WAKE_EXTRA = "WAKE-:-01-07A"
WAKE_COMBINED = "WAKE-:-01-07 & WAKE-:-01-07A"

METRICS = ["TOTPOP", "G24PREDHAR", "G24PRERTRU"]

print("Reading validated NC block master...")

blocks = pd.read_csv(
    BLOCKS,
    dtype={"GEOID20": str, "PRECINCTID": str},
    usecols=[
        "GEOID20", "PRECINCTID",
        "DISTRICT_2023", *METRICS
    ],
)

if len(blocks) != EXPECTED_BLOCKS or not blocks.GEOID20.is_unique:
    raise ValueError("Missing or duplicate Census blocks")

if blocks.isna().any().any() or (blocks[METRICS] < 0).any().any():
    raise ValueError("Missing or negative block values")

if tuple(int(blocks[x].sum()) for x in METRICS) != EXPECTED_TOTALS:
    raise ValueError("Statewide population or vote totals changed")

if set(blocks.DISTRICT_2023) != set(range(1, 15)):
    raise ValueError("Unexpected 2023 congressional districts")

# Keep the ambiguous Wake block with both adjacent precincts.
# This preserves all population and votes without inventing a split.
blocks["PRECINCT_KEY"] = blocks.PRECINCTID.replace(
    {WAKE_COMBINED: WAKE_ORIGINAL}
)

aggregates = (
    blocks.groupby(
        ["PRECINCT_KEY", "DISTRICT_2023"], as_index=False
    )
    .agg(
        BLOCK_COUNT=("GEOID20", "size"),
        TOTPOP=("TOTPOP", "sum"),
        G24PREDHAR=("G24PREDHAR", "sum"),
        G24PRERTRU=("G24PRERTRU", "sum"),
    )
)

expected_keys = set(zip(
    aggregates.PRECINCT_KEY,
    aggregates.DISTRICT_2023
))

by_precinct = (
    aggregates.groupby("PRECINCT_KEY")
    .DISTRICT_2023.apply(set)
    .to_dict()
)

print("Reading congressional precinct geometries...")

features = gpd.read_file(SHAPE, columns=["UNIQUE_ID"])

if len(features) != 2678 or not features.UNIQUE_ID.is_unique:
    raise ValueError("Unexpected congressional precinct geometry IDs")

if features.crs is None or not features.geometry.is_valid.all():
    raise ValueError("Missing CRS or invalid precinct polygons")

wake_rows = features.set_index("UNIQUE_ID").geometry

wake_union = (
    wake_rows.loc[WAKE_ORIGINAL]
    .union(wake_rows.loc[WAKE_EXTRA])
)

if wake_union.is_empty or not wake_union.is_valid:
    raise ValueError("Wake precinct union is invalid")

plan = gpd.read_file(
    PLAN, columns=["DISTRICT"]
).to_crs(features.crs)

plan["DISTRICT"] = plan.DISTRICT.astype(int)

if len(plan) != 14 or set(plan.DISTRICT) != set(range(1, 15)):
    raise ValueError("Unexpected 2023 district boundaries")

district_shapes = dict(zip(plan.DISTRICT, plan.geometry))

parts = []
actual_splits = set()

suffix = re.compile(r"(.+)-\(CON-(\d{2})\)$")

for feature in features.itertuples(index=False):
    name = feature.UNIQUE_ID

    if name == WAKE_EXTRA:
        continue

    geom = wake_union if name == WAKE_ORIGINAL else feature.geometry

    found = suffix.fullmatch(name)
    base = found.group(1) if found else name

    districts = by_precinct.get(base)

    if districts is None:
        raise ValueError(f"No block data for geometry: {name}")

    if found:
        district = int(found.group(2))
        candidate_parts = [(district, geom)]

    elif len(districts) == 1:
        candidate_parts = [(next(iter(districts)), geom)]

    else:
        actual_splits.add(base)

        candidate_parts = [
            (
                district,
                geom.intersection(district_shapes[district])
            )
            for district in sorted(districts)
        ]

        combined_area = sum(
            piece.area for _, piece in candidate_parts
        )

        tolerance = max(1e-3, 1e-6 * geom.area)

        if abs(combined_area - geom.area) > tolerance:
            raise ValueError(
                f"Incomplete district intersection: {base}"
            )

    for district, piece in candidate_parts:
        if (base, district) not in expected_keys:
            raise ValueError(
                f"Geometry without matching block group: "
                f"{base}, {district}"
            )

        if piece.is_empty or not piece.is_valid or piece.area <= 0:
            raise ValueError(
                f"Invalid geometry for {base}, district {district}"
            )

        parts.append({
            "PRECINCT_KEY": base,
            "DISTRICT_2023": district,
            "geometry": piece,
        })

if actual_splits != EXTRA_SPLITS:
    raise ValueError(
        f"Unexpected missing geometry splits: {actual_splits}"
    )

units = gpd.GeoDataFrame(
    parts, geometry="geometry", crs=features.crs
)

actual_keys = list(zip(
    units.PRECINCT_KEY,
    units.DISTRICT_2023
))

if len(actual_keys) != len(set(actual_keys)):
    raise ValueError("Duplicate geographic unit keys")

if set(actual_keys) != expected_keys or len(units) != EXPECTED_UNITS:
    raise ValueError(
        "Geographic unit and block aggregate coverage mismatch"
    )

units = units.merge(
    aggregates,
    on=["PRECINCT_KEY", "DISTRICT_2023"],
    how="left",
    validate="one_to_one",
)

units["CONG_DIST"] = (
    units.DISTRICT_2023.astype(str).str.zfill(2)
)

units["UNIT_ID"] = (
    units.PRECINCT_KEY + "|" + units.CONG_DIST
)

if units[METRICS].isna().any().any():
    raise ValueError("Missing population or vote values")

if tuple(int(units[x].sum()) for x in METRICS) != EXPECTED_TOTALS:
    raise ValueError("Statewide totals changed after geometry join")

# Compare district totals to the independently built block summary.
reference = pd.read_csv(COMPARISON)
reference = (
    reference.loc[reference.plan_year == 2023]
    .set_index("district")
)

actual = units.groupby("DISTRICT_2023")[METRICS].sum()

for district in range(1, 15):
    for column, source_column in [
        ("TOTPOP", "population"),
        ("G24PREDHAR", "harris_votes"),
        ("G24PRERTRU", "trump_votes"),
    ]:
        if int(actual.loc[district, column]) != int(
            reference.loc[district, source_column]
        ):
            raise ValueError(
                f"District {district} total mismatch: {column}"
            )

OUTPUT.parent.mkdir(parents=True, exist_ok=True)

units[
    [
        "UNIT_ID", "PRECINCT_KEY", "CONG_DIST",
        "BLOCK_COUNT", *METRICS, "geometry"
    ]
].to_file(
    OUTPUT,
    layer="precincts",
    driver="GPKG",
)

print(f"Geographic units: {len(units):,}")
print(
    "Additional split precincts:",
    ", ".join(sorted(actual_splits))
)
print(f"Population: {int(units.TOTPOP.sum()):,}")
print(f"Harris votes: {int(units.G24PREDHAR.sum()):,}")
print(f"Trump votes: {int(units.G24PRERTRU.sum()):,}")
print("14 district totals agree with the block-level comparison")
print(f"Saved: {OUTPUT}")
print("Geographic totals validated; graph connectivity still needs testing")
