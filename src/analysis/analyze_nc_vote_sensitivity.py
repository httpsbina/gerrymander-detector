"""Analyze hypothetical uniform vote swings for NC enacted maps."""

from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "data/processed/nc_plan_comparison.csv"
OUTPUT = ROOT / "outputs/analysis/nc_vote_swing_sensitivity.csv"

plans = pd.read_csv(SOURCE)

required = {
    "plan_year", "district", "harris_votes", "trump_votes"
}

if not required.issubset(plans.columns):
    raise ValueError("Missing election columns")

if len(plans) != 28 or plans.duplicated(
    ["plan_year", "district"]
).any():
    raise ValueError("Invalid enacted plan data")

rows = []

for year in (2023, 2025):
    p = plans[plans.plan_year == year].sort_values("district")

    if p.district.tolist() != list(range(1, 15)):
        raise ValueError(f"Invalid districts: {year}")

    h = p.harris_votes.astype(float)
    t = p.trump_votes.astype(float)

    if (h.lt(0) | t.lt(0) | (h + t).le(0)).any():
        raise ValueError(f"Invalid votes: {year}")

    share = h / (h + t)
    baseline = share > 0.5

    if int(baseline.sum()) != 3:
        raise ValueError(f"Unexpected baseline: {year}")

    for swing in range(-3, 4):
        winners = share + swing / 100 > 0.5

        flips = p.loc[
            winners != baseline, "district"
        ].astype(int).tolist()

        rows.append({
            "starting_map": year,
            "harris_swing_pp": swing,
            "harris_seats": int(winners.sum()),
            "flipped_districts": ",".join(map(str, flips))
        })

result = pd.DataFrame(rows)

expected = {(2023, 2): 4, (2025, 2): 3}

for (year, swing), seats in expected.items():
    actual = result.loc[
        (result.starting_map == year)
        & (result.harris_swing_pp == swing),
        "harris_seats"
    ].iloc[0]

    if actual != seats:
        raise ValueError(
            f"Unexpected result: {year}, {swing}"
        )

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
result.to_csv(OUTPUT, index=False)

print("\nNC VOTE-SWING SENSITIVITY")
print("=" * 60)
print(result.to_string(index=False))
print("\nAll checks passed.")
print(f"Saved: {OUTPUT}")
print("Hypothetical scenario only, not election-data validation.")
