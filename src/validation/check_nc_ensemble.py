"""Validate North Carolina ReCom output across checkpoint segments."""

import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "outputs/ensembles"

FILES = sorted(OUTPUT.glob(
    "north_carolina_chain_eps0p01_seed101_steps*.csv"
))

EXPECTED_POP = 10_439_388
DISTRICTS = 14
EPSILON = 0.01
IDEAL_POP = EXPECTED_POP / DISTRICTS

REQUIRED = {
    "step", "seed", "epsilon", "dem_seats",
    "min_pop", "max_pop", "max_abs_pop_dev",
    "plan_hash", "cut_edges"
}

if not FILES:
    raise FileNotFoundError("No NC chain CSV files found")

frames = []

for path in FILES:
    match = re.search(r"steps(\d+)-(\d+)\.csv$", path.name)

    if not match:
        raise ValueError(f"Unexpected filename: {path.name}")

    first, last = map(int, match.groups())

    df = pd.read_csv(path)

    if not REQUIRED <= set(df.columns):
        raise ValueError(f"Missing columns in {path.name}")

    if df.isna().any().any():
        raise ValueError(f"Missing values in {path.name}")

    if df["step"].tolist() != list(range(first, last + 1)):
        raise ValueError(f"Step mismatch in {path.name}")

    if not (df["seed"] == 101).all():
        raise ValueError("Unexpected random seed")

    if not ((df["epsilon"] - EPSILON).abs() < 1e-10).all():
        raise ValueError("Unexpected population tolerance")

    frames.append(df)

    print(f"{path.name}: {len(df)} states")

data = pd.concat(frames, ignore_index=True)
data = data.sort_values("step").reset_index(drop=True)

if data["step"].tolist() != list(range(len(data))):
    raise ValueError("Missing or duplicate chain steps")

if not data["dem_seats"].between(0, DISTRICTS).all():
    raise ValueError("Invalid Democratic seat count")

if not (data["min_pop"] <= data["max_pop"]).all():
    raise ValueError("Invalid population range")

if not data["plan_hash"].astype(str).str.fullmatch(
    r"[0-9a-f]{64}"
).all():
    raise ValueError("Invalid plan fingerprint")

computed_deviation = pd.concat([
    (data["min_pop"] / IDEAL_POP - 1).abs(),
    (data["max_pop"] / IDEAL_POP - 1).abs()
], axis=1).max(axis=1)

if not (
    (computed_deviation - data["max_abs_pop_dev"]).abs()
    < 1e-9
).all():
    raise ValueError("Population deviation calculation mismatch")

if (data["max_abs_pop_dev"] > EPSILON + 1e-10).any():
    raise ValueError("Population tolerance exceeded")

if int(data.iloc[0]["dem_seats"]) != 3:
    raise ValueError("Initial seed does not match the 2023 plan")

unique = data["plan_hash"].nunique()
duplicates = len(data) - unique

print("\nCombined NC ensemble:")
print(f"Recorded states: {len(data)}")
print(f"Steps: {data.step.min()} through {data.step.max()}")
print(f"Unique plans: {unique}")
print(f"Repeated plans: {duplicates}")
print(f"Mean Democratic seats: {data.dem_seats.mean():.3f}")
print(f"Maximum deviation: {data.max_abs_pop_dev.max():.6%}")

print("\nDemocratic seat distribution:")
print(data["dem_seats"].value_counts().sort_index().to_string())

print("\nNC ensemble validation passed")
