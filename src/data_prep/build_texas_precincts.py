"""
build_texas_precincts.py

Builds the validated Texas precinct-level dataset used by GerryChain.

Population and election data are aggregated from the canonical
2020 Census block master dataset to the 2024 election precincts.

No centroid population assignment is used.

PLANC2333 remains a block-level benchmark. We do NOT force a C2333
district label onto precincts that are split by the 2025 plan.
"""

import os
import pandas as pd
import geopandas as gpd

try:
    from shapely import make_valid
except ImportError:
    from shapely.validation import make_valid


ROOT = os.path.join(
    os.path.expanduser("~"),
    "OneDrive",
    "Documents",
    "gerrymander-detector",
)

MASTER_PATH = os.path.join(
    ROOT,
    "data",
    "processed",
    "tx_blocks_master.csv",
)

GEOMETRY_PATH = os.path.join(
    ROOT,
    "data",
    "raw",
    "election_results",
    "tx_2024_gen_all_tx_vtd",
    "tx_2024_gen_all_tx_vtd.shp",
)

SEED_PATH = os.path.join(
    ROOT,
    "data",
    "raw",
    "election_results",
    "tx_2024_gen_cong_tx_vtd",
    "tx_2024_gen_cong_tx_vtd.shp",
)

OUTPUT_PATH = os.path.join(
    ROOT,
    "data",
    "processed",
    "tx_precincts_validated.gpkg",
)


EXPECTED_BLOCKS = 668_757
EXPECTED_PRECINCTS = 9_712
EXPECTED_POP = 29_145_505
EXPECTED_VAP = 21_866_700
EXPECTED_HARRIS = 4_835_134
EXPECTED_TRUMP = 6_393_403
EXPECTED_DISTRICTS = 38


print("loading validated block master...")

blocks = pd.read_csv(
    MASTER_PATH,
    dtype={
        "GEOID20": str,
        "STATEFP": str,
        "COUNTYFP": str,
        "PRECINCTID": str,
    },
)

assert len(blocks) == EXPECTED_BLOCKS
assert blocks["GEOID20"].is_unique
assert blocks["PRECINCTID"].notna().all()

print(f"  {len(blocks):,} blocks")
print(
    f"  unique precincts: "
    f"{blocks['PRECINCTID'].nunique():,}"
)


print("\naggregating blocks to 2024 precincts...")

precinct_data = (
    blocks
    .groupby("PRECINCTID", as_index=False)
    .agg(
        TOTPOP=("TOTPOP", "sum"),
        VAP=("VAP", "sum"),
        G24PREDHAR=("G24PREDHAR", "sum"),
        G24PRERTRU=("G24PRERTRU", "sum"),
        BLOCK_COUNT=("GEOID20", "size"),
        C2333_NDIST=("C2333", "nunique"),
    )
)

precinct_data["C2333_SPLIT"] = (
    precinct_data["C2333_NDIST"] > 1
)

assert len(precinct_data) == EXPECTED_PRECINCTS
assert precinct_data["PRECINCTID"].is_unique
assert precinct_data["TOTPOP"].sum() == EXPECTED_POP
assert precinct_data["VAP"].sum() == EXPECTED_VAP
assert precinct_data["G24PREDHAR"].sum() == EXPECTED_HARRIS
assert precinct_data["G24PRERTRU"].sum() == EXPECTED_TRUMP

print(f"  {len(precinct_data):,} precincts")
print(f"  population: {precinct_data['TOTPOP'].sum():,}")
print(f"  VAP: {precinct_data['VAP'].sum():,}")
print(f"  Harris: {precinct_data['G24PREDHAR'].sum():,}")
print(f"  Trump:  {precinct_data['G24PRERTRU'].sum():,}")

split_count = int(
    precinct_data["C2333_SPLIT"].sum()
)

print(
    f"  precincts intersecting multiple "
    f"C2333 districts: {split_count:,}"
)


print("\nloading 2024 precinct geometry...")

geometry = gpd.read_file(
    GEOMETRY_PATH
)

geometry["UNIQUE_ID"] = (
    geometry["UNIQUE_ID"]
    .astype(str)
)

assert len(geometry) == EXPECTED_PRECINCTS
assert geometry["UNIQUE_ID"].is_unique

invalid_before = (
    ~geometry.geometry.is_valid
)

print(f"  {len(geometry):,} geometries")
print(
    f"  invalid geometries before repair: "
    f"{invalid_before.sum():,}"
)

if invalid_before.any():

    print("  repairing invalid geometries...")

    geometry.loc[
        invalid_before,
        "geometry",
    ] = (
        geometry.loc[
            invalid_before,
            "geometry",
        ]
        .apply(make_valid)
    )

invalid_after = (
    ~geometry.geometry.is_valid
)

empty_after = (
    geometry.geometry.is_empty
)

print(
    f"  invalid geometries after repair: "
    f"{invalid_after.sum():,}"
)

print(
    f"  empty geometries: "
    f"{empty_after.sum():,}"
)

assert not invalid_after.any()
assert not empty_after.any()


print("\nloading congressional seed assignment...")

seed_assignment = gpd.read_file(
    SEED_PATH,
    ignore_geometry=True,
)

seed_assignment["UNIQUE_ID"] = (
    seed_assignment["UNIQUE_ID"]
    .astype(str)
)

seed_assignment["CONG_DIST"] = (
    seed_assignment["CONG_DIST"]
    .astype(str)
    .str.zfill(2)
)

seed_assignment = seed_assignment[
    [
        "UNIQUE_ID",
        "CONG_DIST",
    ]
].copy()

assert len(seed_assignment) == EXPECTED_PRECINCTS
assert seed_assignment["UNIQUE_ID"].is_unique
assert (
    seed_assignment["CONG_DIST"].nunique()
    == EXPECTED_DISTRICTS
)

geometry = geometry.merge(
    seed_assignment,
    on="UNIQUE_ID",
    how="left",
    validate="one_to_one",
)

assert geometry["CONG_DIST"].notna().all()

print(
    f"  seed districts: "
    f"{geometry['CONG_DIST'].nunique()}"
)


print("\njoining validated data to geometry...")

keep_columns = [
    column
    for column in [
        "UNIQUE_ID",
        "COUNTYFP",
        "County",
        "TX_VTD",
        "CONG_DIST",
        "geometry",
    ]
    if column in geometry.columns
]

geometry = geometry[
    keep_columns
].copy()

precincts = geometry.merge(
    precinct_data,
    left_on="UNIQUE_ID",
    right_on="PRECINCTID",
    how="left",
    validate="one_to_one",
)

assert len(precincts) == EXPECTED_PRECINCTS

assert precincts[
    "TOTPOP"
].notna().all()

assert precincts[
    "VAP"
].notna().all()

assert (
    precincts["TOTPOP"].sum()
    == EXPECTED_POP
)

assert (
    precincts["VAP"].sum()
    == EXPECTED_VAP
)

assert (
    precincts["G24PREDHAR"].sum()
    == EXPECTED_HARRIS
)

assert (
    precincts["G24PRERTRU"].sum()
    == EXPECTED_TRUMP
)

print("  join validation passed")


print("\nstatewide validation:")

print(
    f"  population: "
    f"{precincts['TOTPOP'].sum():,}"
)

print(
    f"  VAP: "
    f"{precincts['VAP'].sum():,}"
)

print(
    f"  Harris: "
    f"{precincts['G24PREDHAR'].sum():,}"
)

print(
    f"  Trump: "
    f"{precincts['G24PRERTRU'].sum():,}"
)

zero_pop = int(
    (precincts["TOTPOP"] == 0).sum()
)

print(
    f"  zero-population precincts: "
    f"{zero_pop:,}"
)


print(
    "\n2024 congressional district assignment "
    "(seed map only):"
)

seed_summary = (
    precincts
    .groupby("CONG_DIST")
    .agg(
        POP=("TOTPOP", "sum"),
        VAP=("VAP", "sum"),
        HARRIS=("G24PREDHAR", "sum"),
        TRUMP=("G24PRERTRU", "sum"),
    )
)

assert (
    len(seed_summary)
    == EXPECTED_DISTRICTS
)

ideal = (
    EXPECTED_POP
    / EXPECTED_DISTRICTS
)

seed_summary["POP_DEV"] = (
    seed_summary["POP"]
    / ideal
    - 1
)

seed_summary["DEM_SHARE"] = (
    seed_summary["HARRIS"]
    / (
        seed_summary["HARRIS"]
        + seed_summary["TRUMP"]
    )
)

print(
    seed_summary.to_string()
)

print(
    f"\n  seed districts: "
    f"{len(seed_summary)}"
)

print(
    "  seed population range: "
    f"{seed_summary['POP'].min():,} - "
    f"{seed_summary['POP'].max():,}"
)

print(
    "  max absolute seed population deviation: "
    f"{seed_summary['POP_DEV'].abs().max():.6%}"
)

seed_harris_wins = int(
    (
        seed_summary["HARRIS"]
        > seed_summary["TRUMP"]
    ).sum()
)

print(
    "  Harris > Trump seed districts: "
    f"{seed_harris_wins}/"
    f"{EXPECTED_DISTRICTS}"
)


print("\nsaving validated precinct dataset...")

os.makedirs(
    os.path.dirname(
        OUTPUT_PATH
    ),
    exist_ok=True,
)

precincts.to_file(
    OUTPUT_PATH,
    layer="precincts",
    driver="GPKG",
)

print("saved to:")
print(f"  {OUTPUT_PATH}")

print("\ndone!")