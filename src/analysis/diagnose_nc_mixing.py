"""Diagnose mixing of the extended North Carolina ReCom chains."""

import re
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "outputs/ensembles"
SEEDS = (101, 202, 303)
STEPS = 2000
WARMUP = 500
METRICS = ("dem_seats", "efficiency_gap", "cut_edges")


def approximate_ess(values):
    values = np.asarray(values, dtype=float)
    n = len(values)
    centered = values - values.mean()

    if n < 4 or np.all(centered == 0):
        return float("nan")

    autocov = np.correlate(
        centered, centered, mode="full"
    )[n - 1:]

    autocov = autocov / np.arange(n, 0, -1)
    rho = autocov / autocov[0]

    tau = 1.0

    for lag in range(1, n - 1, 2):
        pair = rho[lag] + rho[lag + 1]

        if pair <= 0:
            break

        tau += 2.0 * pair

    return min(float(n), n / tau)


def split_rhat(values):
    chains, draws = values.shape
    if chains < 2 or draws < 4:
        raise ValueError("Insufficient chains or draws")

    half = draws // 2

    split = np.concatenate(
        [values[:, :half], values[:, -half:]],
        axis=0,
    )

    within = split.var(axis=1, ddof=1).mean()

    if within == 0:
        return float("nan")

    between = half * split.mean(axis=1).var(ddof=1)
    estimated = ((half - 1) * within + between) / half

    return float(np.sqrt(estimated / within))


runs = {}

for seed in SEEDS:
    files = sorted(SOURCE.glob(
        f"north_carolina_chain_eps0p01_seed{seed}_steps*.csv"
    ))

    frames = []

    for path in files:
        match = re.search(
            r"steps(\d+)-(\d+)\.csv$", path.name
        )

        if match is None:
            raise ValueError(f"Unexpected filename: {path.name}")

        first, last = map(int, match.groups())
        frame = pd.read_csv(path)

        if frame.step.tolist() != list(range(first, last + 1)):
            raise ValueError(f"Invalid step range: {path.name}")

        if not (frame.seed == seed).all():
            raise ValueError(f"Unexpected seed: {path.name}")

        if frame[list(METRICS)].isna().any().any():
            raise ValueError(f"Missing values: {path.name}")

        frames.append(frame)

    if not frames:
        raise FileNotFoundError(f"No CSV files for seed {seed}")

    run = pd.concat(frames, ignore_index=True)
    run = run.sort_values("step").reset_index(drop=True)

    if run.step.tolist() != list(range(STEPS)):
        raise ValueError(f"Missing or duplicate steps: {seed}")

    runs[seed] = run.iloc[WARMUP:].reset_index(drop=True)

print("NORTH CAROLINA MIXING DIAGNOSTICS")
print(f"Chains: {len(SEEDS)}")
print(f"Warmup excluded per chain: {WARMUP}")
print(f"Remaining states per chain: {STEPS - WARMUP}")
print(f"Total post-warmup states: {len(SEEDS) * (STEPS - WARMUP)}")

for metric in METRICS:
    values = np.stack([
        runs[seed][metric].to_numpy(dtype=float)
        for seed in SEEDS
    ])

    ess_by_chain = [
        approximate_ess(chain) for chain in values
    ]

    rhat = split_rhat(values)

    print(f"\nMetric: {metric}")
    print(f"  Provisional split-Rhat: {rhat:.4f}")

    for seed, ess in zip(SEEDS, ess_by_chain):
        print(
            f"  Seed {seed} approximate ESS: "
            f"{ess:.1f} / {values.shape[1]}"
        )

    print(
        "  Sum of approximate chain ESS: "
        f"{sum(ess_by_chain):.1f}"
    )

print("\nRare seat outcomes after warmup:")

for seed in SEEDS:
    series = runs[seed].dem_seats
    rare = int((series <= 3).sum())

    print(
        f"  Seed {seed}: {rare} states with 3 or fewer "
        f"Harris-won districts out of {len(series)}"
    )

print("\nThese diagnostics do not establish full plan-space mixing.")
print("Approximate ESS is not rank-normalized bulk/tail ESS.")
print("NC mixing diagnostics completed")
