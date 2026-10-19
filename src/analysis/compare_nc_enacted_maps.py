"""Compare enacted 2023 and 2025 NC congressional district outcomes."""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "data/processed/nc_plan_comparison.csv"
BLOCKS = ROOT / "data/processed/nc_blocks_master.csv"
OUTPUT = ROOT / "outputs/analysis/nc_enacted_map_comparison.csv"

summary = pd.read_csv(SOURCE)
blocks = pd.read_csv(
    BLOCKS,
    usecols=["GEOID20", "DISTRICT_2023", "DISTRICT_2025"],
    dtype={"GEOID20": str},
)

expected = {2023, 2025}

if set(summary.plan_year) != expected:
    raise ValueError("Expected the 2023 and 2025 plans")

if len(blocks) != 236638 or not blocks.GEOID20.is_unique:
    raise ValueError("Census block coverage mismatch")

if summary.duplicated(["plan_year", "district"]).any():
    raise ValueError("Duplicate district summary rows")

plans = {}

for year in sorted(expected):
    plan = summary.loc[
        summary.plan_year == year
    ].set_index("district").sort_index()

    if list(plan.index) != list(range(1, 15)):
        raise ValueError(f"Missing districts in {year}")

    totals = (
        int(plan.population.sum()),
        int(plan.harris_votes.sum()),
        int(plan.trump_votes.sum())
    )

    if totals != (10439388, 2713609, 2896942):
        raise ValueError(f"Statewide totals mismatch in {year}")

    plans[year] = plan

changed = int(
    (blocks.DISTRICT_2023 != blocks.DISTRICT_2025).sum()
)

if changed != 18826:
    raise ValueError(f"Unexpected reassigned block count: {changed}")

report = pd.DataFrame({
    "district": range(1, 15)
})

for year in sorted(expected):
    plan = plans[year]
    harris = plan.harris_votes
    trump = plan.trump_votes

    report[f"harris_share_{year}"] = (
        100 * harris / (harris + trump)
    ).to_numpy()

    report[f"harris_votes_{year}"] = harris.to_numpy()
    report[f"trump_votes_{year}"] = trump.to_numpy()

    seats = int((harris > trump).sum())
    print(f"{year}: {seats} Harris-won districts")

report["share_change_pp"] = (
    report.harris_share_2025 - report.harris_share_2023
)

report["winner_2023"] = (
    report.harris_share_2023 > 50
).map({True: "Harris", False: "Trump"})

report["winner_2025"] = (
    report.harris_share_2025 > 50
).map({True: "Harris", False: "Trump"})

report["winner_changed"] = (
    report.winner_2023 != report.winner_2025
)

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
report.to_csv(OUTPUT, index=False)

print(f"\nReassigned Census blocks: {changed:,}")
print(f"District winners changed: {report.winner_changed.sum()}")

print("\n2023 TO 2025 DISTRICT COMPARISON")
print(
    report[
        [
            "district",
            "harris_share_2023",
            "harris_share_2025",
            "share_change_pp",
            "winner_changed",
        ]
    ].round(3).to_string(index=False)
)

print(f"\nSaved: {OUTPUT}")
print("NC enacted map comparison passed")
