"""Audit block, population, and vote flows between NC congressional maps."""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "data/processed/nc_blocks_master.csv"
OUTPUT = ROOT / "outputs/analysis/nc_2025_reassignment_flows.csv"

columns = [
    "GEOID20", "COUNTYFP", "DISTRICT_2023", "DISTRICT_2025",
    "TOTPOP", "G24PREDHAR", "G24PRERTRU"
]

blocks = pd.read_csv(
    SOURCE,
    usecols=columns,
    dtype={"GEOID20": str, "COUNTYFP": str},
)

if len(blocks) != 236638 or not blocks.GEOID20.is_unique:
    raise ValueError("Invalid Census block coverage")

if blocks[columns].isna().any().any():
    raise ValueError("Missing values in Census block master")

metrics = ["TOTPOP", "G24PREDHAR", "G24PRERTRU"]

if (blocks[metrics] < 0).any().any():
    raise ValueError("Negative population or votes")

totals = tuple(int(blocks[c].sum()) for c in metrics)

if totals != (10439388, 2713609, 2896942):
    raise ValueError("Statewide population or vote totals mismatch")

changed = blocks.loc[
    blocks.DISTRICT_2023 != blocks.DISTRICT_2025
].copy()

if len(changed) != 18826:
    raise ValueError("Unexpected number of reassigned blocks")

flows = (
    changed.groupby(
        ["DISTRICT_2023", "DISTRICT_2025"],
        as_index=False
    )
    .agg(
        blocks=("GEOID20", "count"),
        population=("TOTPOP", "sum"),
        harris_votes=("G24PREDHAR", "sum"),
        trump_votes=("G24PRERTRU", "sum"),
    )
    .sort_values("population", ascending=False)
)

if int(flows.blocks.sum()) != len(changed):
    raise ValueError("Flow block count mismatch")

if int(flows.population.sum()) != int(changed.TOTPOP.sum()):
    raise ValueError("Flow population mismatch")

if int(flows.harris_votes.sum()) != int(changed.G24PREDHAR.sum()):
    raise ValueError("Flow Harris vote mismatch")

if int(flows.trump_votes.sum()) != int(changed.G24PRERTRU.sum()):
    raise ValueError("Flow Trump vote mismatch")

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
flows.to_csv(OUTPUT, index=False)

print("NC 2023 -> 2025 CONGRESSIONAL REASSIGNMENTS")
print(f"Changed blocks: {len(changed):,}")
print(f"Share of all blocks: {100 * len(changed) / len(blocks):.3f}%")
print(f"Population in changed blocks: {int(changed.TOTPOP.sum()):,}")
print(f"Share of state population: {100 * changed.TOTPOP.sum() / blocks.TOTPOP.sum():.3f}%")
print(f"Allocated Harris votes: {int(changed.G24PREDHAR.sum()):,}")
print(f"Allocated Trump votes: {int(changed.G24PRERTRU.sum()):,}")

print("\nDISTRICT TRANSFERS")
print(flows.to_string(index=False))

print("\nMOST AFFECTED COUNTIES")
counties = (
    changed.groupby("COUNTYFP")
    .agg(
        blocks=("GEOID20", "count"),
        population=("TOTPOP", "sum")
    )
    .sort_values("population", ascending=False)
)

print(counties.head(10).to_string())

print(f"\nSaved: {OUTPUT}")
print("NC district reassignment audit passed")
