"""Check whether 2023-based NC units can represent the 2025 plan."""

from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "data/processed/nc_blocks_master.csv"

blocks = pd.read_csv(
    SOURCE,
    usecols=[
        "GEOID20", "PRECINCTID", "TOTPOP",
        "DISTRICT_2023", "DISTRICT_2025"
    ],
    dtype={"GEOID20": str, "PRECINCTID": str}
)

if len(blocks) != 236638 or not blocks.GEOID20.is_unique:
    raise ValueError("Invalid block coverage")

if blocks.isna().any().any():
    raise ValueError("Missing values")

blocks["PRECINCT_KEY"] = blocks.PRECINCTID.replace({
    "WAKE-:-01-07 & WAKE-:-01-07A": "WAKE-:-01-07"
})

blocks["UNIT_ID"] = (
    blocks.PRECINCT_KEY + "|" +
    blocks.DISTRICT_2023.astype(str).str.zfill(2)
)

if blocks.UNIT_ID.nunique() != 2680:
    raise ValueError("Unexpected number of geographic units")

if int(blocks.TOTPOP.sum()) != 10439388:
    raise ValueError("Population mismatch")

flows = (
    blocks.groupby(["UNIT_ID", "DISTRICT_2025"])
    .agg(
        population=("TOTPOP", "sum"),
        blocks=("GEOID20", "size")
    )
    .reset_index()
)

district_counts = flows.groupby("UNIT_ID").size()
mixed_ids = district_counts[district_counts > 1].index

mixed = flows[flows.UNIT_ID.isin(mixed_ids)]

mixed_population = int(mixed.population.sum())
mixed_blocks = int(mixed.blocks.sum())

minimum_mismatch = int(
    (
        mixed.groupby("UNIT_ID").population.sum()
        - mixed.groupby("UNIT_ID").population.max()
    ).sum()
)

print("NC 2025 PLAN - GEOGRAPHIC UNIT COMPATIBILITY")
print(f"2023-based units: {blocks.UNIT_ID.nunique():,}")
print(f"Units spanning multiple 2025 districts: {len(mixed_ids):,}")
print(f"Blocks in spanning units: {mixed_blocks:,}")
print(f"Population in spanning units: {mixed_population:,}")
print(
    "Minimum misassigned population if units remain intact: "
    f"{minimum_mismatch:,}"
)

if len(mixed_ids):
    largest = (
        mixed.groupby("UNIT_ID").population.sum()
        .sort_values(ascending=False)
        .head(10)
    )

    print("\nLARGEST MIXED UNITS")

    for unit_id, population in largest.items():
        destinations = sorted(
            mixed.loc[
                mixed.UNIT_ID == unit_id,
                "DISTRICT_2025"
            ].astype(int).tolist()
        )

        print(
            f"{unit_id}: population={population:,}, "
            f"2025 districts={destinations}"
        )

    print(
        "\nThe 2025 plan cannot be represented exactly "
        "using these intact 2023-based units."
    )
else:
    print(
        "\nBlock assignments are compatible with intact units."
    )
    print("Geometric alignment still requires separate verification.")

print("\nNC 2025 unit compatibility audit completed")
