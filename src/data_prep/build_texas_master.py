"""
build_texas_master.py

Builds the  Texas block-level analysis dataset by joining:

1. Official 2020 Census block population
2. RDH 2024 election results disaggregated to 2020 Census blocks
3. Official Texas PLANC2333 block equivalency

This replaces the old centroid-based population crosswalk.
"""

import os
import pandas as pd


ROOT = os.path.join(
    os.path.expanduser("~"),
    "OneDrive",
    "Documents",
    "gerrymander-detector",
)

POP_PATH = os.path.join(
    ROOT,
    "data",
    "raw",
    "shapefiles",
    "Blocks_Pop",
    "Blocks_Pop.txt",
)

ELECTION_PATH = os.path.join(
    ROOT,
    "data",
    "raw",
    "election_results",
    "tx_2024_gen_2020_blocks",
    "tx_2024_gen_2020_blocks.csv",
)

PLAN_PATH = os.path.join(
    ROOT,
    "data",
    "raw",
    "shapefiles",
    "PLANC2333.csv",
)

OUTPUT_PATH = os.path.join(
    ROOT,
    "data",
    "processed",
    "tx_blocks_master.csv",
)


EXPECTED_BLOCKS = 668_757
EXPECTED_POP = 29_145_505
EXPECTED_HARRIS = 4_835_134
EXPECTED_TRUMP = 6_393_403
EXPECTED_DISTRICTS = 38


print("loading official census block population...")

pop = pd.read_csv(
    POP_PATH,
    dtype={"SCTBKEY": str},
    usecols=[
        "SCTBKEY",
        "total",
        "vap",
    ],
)

pop = pop.rename(
    columns={
        "SCTBKEY": "GEOID20",
        "total": "TOTPOP",
        "vap": "VAP",
    }
)

print(f"  {len(pop):,} blocks")
print(f"  population: {pop['TOTPOP'].sum():,}")
print(f"  VAP: {pop['VAP'].sum():,}")


print("\nloading 2024 block-level election results...")

election = pd.read_csv(
    ELECTION_PATH,
    dtype={
        "GEOID20": str,
        "STATEFP": str,
        "COUNTYFP": str,
        "PRECINCTID": str,
    },
    usecols=[
        "GEOID20",
        "STATEFP",
        "COUNTYFP",
        "PRECINCTID",
        "G24PREDHAR",
        "G24PRERTRU",
    ],
)

print(f"  {len(election):,} blocks")
print(f"  Harris: {election['G24PREDHAR'].sum():,}")
print(f"  Trump:  {election['G24PRERTRU'].sum():,}")


print("\nloading official PLANC2333 block equivalency...")

plan = pd.read_csv(
    PLAN_PATH,
    dtype={"SCTBKEY": str},
)

plan = plan.rename(
    columns={
        "SCTBKEY": "GEOID20",
        "DISTRICT": "C2333",
    }
)

print(f"  {len(plan):,} blocks")
print(f"  {plan['C2333'].nunique()} districts")


print("\nvalidating source files...")

assert len(pop) == EXPECTED_BLOCKS
assert len(election) == EXPECTED_BLOCKS
assert len(plan) == EXPECTED_BLOCKS

assert pop["GEOID20"].is_unique
assert election["GEOID20"].is_unique
assert plan["GEOID20"].is_unique

assert pop["TOTPOP"].sum() == EXPECTED_POP
assert election["G24PREDHAR"].sum() == EXPECTED_HARRIS
assert election["G24PRERTRU"].sum() == EXPECTED_TRUMP
assert plan["C2333"].nunique() == EXPECTED_DISTRICTS

print("  source validation passed")


print("\njoining block datasets...")

master = (
    election
    .merge(
        pop,
        on="GEOID20",
        how="inner",
        validate="one_to_one",
    )
    .merge(
        plan,
        on="GEOID20",
        how="inner",
        validate="one_to_one",
    )
)

assert len(master) == EXPECTED_BLOCKS
assert master["TOTPOP"].sum() == EXPECTED_POP
assert master["G24PREDHAR"].sum() == EXPECTED_HARRIS
assert master["G24PRERTRU"].sum() == EXPECTED_TRUMP

print(f"  master rows: {len(master):,}")
print(f"  population:  {master['TOTPOP'].sum():,}")


print("\nvalidating PLANC2333...")

districts = (
    master
    .groupby("C2333")
    .agg(
        POP=("TOTPOP", "sum"),
        VAP=("VAP", "sum"),
        HARRIS=("G24PREDHAR", "sum"),
        TRUMP=("G24PRERTRU", "sum"),
    )
)

ideal = EXPECTED_POP / EXPECTED_DISTRICTS

districts["POP_DEVIATION"] = (
    districts["POP"] / ideal - 1
)

districts["DEM_SHARE"] = (
    districts["HARRIS"]
    / (districts["HARRIS"] + districts["TRUMP"])
)

harris_districts = int(
    (districts["HARRIS"] > districts["TRUMP"]).sum()
)

print(districts.to_string())

print()
print(
    f"population range: "
    f"{districts['POP'].min():,} - "
    f"{districts['POP'].max():,}"
)

print(
    f"max absolute population deviation: "
    f"{districts['POP_DEVIATION'].abs().max():.8%}"
)

print(
    f"Harris > Trump districts: "
    f"{harris_districts}/{EXPECTED_DISTRICTS}"
)


print("\nsaving master dataset...")

os.makedirs(
    os.path.dirname(OUTPUT_PATH),
    exist_ok=True,
)

master.to_csv(
    OUTPUT_PATH,
    index=False,
)

print(f"saved to:")
print(f"  {OUTPUT_PATH}")

print("\ndone!")