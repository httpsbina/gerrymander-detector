"""Compare three North Carolina ReCom chains and assess convergence."""

import re
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "outputs/ensembles"
OUTPUT = ROOT / "outputs/analysis"

SEEDS = [101, 202, 303]
EXPECTED_STEPS = 2000
WARMUP = 500
EPSILON = 0.01

REQUIRED = {
    "step", "seed", "epsilon", "dem_seats",
    "plan_hash", "max_abs_pop_dev"
}

runs = {}
summaries = []

def autocorrelation(values, lag):
    values = np.asarray(values, dtype=float)
    if len(values) <= lag:
        return float("nan")
    if np.std(values) == 0:
        return float("nan")
    return float(np.corrcoef(values[:-lag], values[lag:])[0, 1])

for seed in SEEDS:
    files = sorted(SOURCE.glob(
        f"north_carolina_chain_eps0p01_seed{seed}_steps*.csv"
    ))

    if not files:
        raise FileNotFoundError(f"No chain files for seed {seed}")

    frames = []

    for path in files:
        match = re.search(r"steps(\d+)-(\d+)\.csv$", path.name)
        if match is None:
            raise ValueError(f"Unexpected filename: {path.name}")

        first, last = map(int, match.groups())
        frame = pd.read_csv(path)

        if not REQUIRED.issubset(frame.columns):
            raise ValueError(f"Missing columns: {path.name}")

        if frame[list(REQUIRED)].isna().any().any():
            raise ValueError(f"Missing values: {path.name}")

        if frame.step.tolist() != list(range(first, last + 1)):
            raise ValueError(f"Nonconsecutive steps: {path.name}")

        if not (frame.seed == seed).all():
            raise ValueError(f"Wrong seed: {path.name}")

        if not np.allclose(frame.epsilon, EPSILON, atol=1e-10):
            raise ValueError(f"Wrong epsilon: {path.name}")

        if (frame.max_abs_pop_dev > EPSILON + 1e-10).any():
            raise ValueError(f"Population tolerance exceeded: {path.name}")

        if not frame.plan_hash.astype(str).str.fullmatch(
            r"[0-9a-f]{64}"
        ).all():
            raise ValueError(f"Invalid plan hash: {path.name}")

        frames.append(frame)
        print(f"Loaded: {path.name}")

    run = (
        pd.concat(frames, ignore_index=True)
        .sort_values("step")
        .reset_index(drop=True)
    )

    if run.step.tolist() != list(range(EXPECTED_STEPS)):
        raise ValueError(f"Missing or duplicate steps for seed {seed}")

    if not run.dem_seats.between(0, 14).all():
        raise ValueError(f"Invalid seat counts for seed {seed}")

    runs[seed] = run
    post = run.iloc[WARMUP:]

    summaries.append({
        "seed": seed,
        "states": len(run),
        "unique_plans": run.plan_hash.nunique(),
        "mean_all": run.dem_seats.mean(),
        "mean_first100": run.iloc[:100].dem_seats.mean(),
        "mean_last100": run.iloc[-100:].dem_seats.mean(),
        "mean_post500": post.dem_seats.mean(),
        "lag1_post500": autocorrelation(post.dem_seats, 1),
        "lag10_post500": autocorrelation(post.dem_seats, 10),
    })

# All three runs intentionally start from the same enacted plan.
initial_hashes = {runs[s].iloc[0].plan_hash for s in SEEDS}

if len(initial_hashes) != 1:
    raise ValueError("Chains do not share the expected seed map")

if any(int(runs[s].iloc[0].dem_seats) != 3 for s in SEEDS):
    raise ValueError("Unexpected enacted-plan seat count")

combined = pd.concat(
    [runs[seed] for seed in SEEDS],
    ignore_index=True
)

hash_counts = Counter(
    fingerprint
    for seed in SEEDS
    for fingerprint in set(runs[seed].plan_hash)
)

shared_across_chains = sum(
    count > 1 for count in hash_counts.values()
)

unique_total = combined.plan_hash.nunique()

# Provisional classical split-Rhat diagnostic on seat counts.
# Exclude the first 100 states and split each remaining chain in half.
halves = []

for seed in SEEDS:
    values = runs[seed].dem_seats.to_numpy(dtype=float)
    remaining = values[WARMUP:]
    midpoint = len(remaining) // 2
    halves.extend([
        remaining[:midpoint],
        remaining[midpoint:]
    ])

samples = np.stack(halves)
n = samples.shape[1]

within = samples.var(axis=1, ddof=1).mean()
between = n * samples.mean(axis=1).var(ddof=1)

if within > 0:
    variance_estimate = (n - 1) / n * within + between / n
    rhat = np.sqrt(variance_estimate / within)
else:
    rhat = float("nan")

summary = pd.DataFrame(summaries)

frequency = pd.crosstab(
    combined.dem_seats,
    combined.seed
).reindex(columns=SEEDS, fill_value=0)

post500 = pd.concat(
    [runs[s].iloc[WARMUP:] for s in SEEDS],
    ignore_index=True
)

post_frequency = pd.crosstab(
    post500.dem_seats,
    post500.seed
).reindex(columns=SEEDS, fill_value=0)

OUTPUT.mkdir(parents=True, exist_ok=True)

summary.to_csv(
    OUTPUT / "nc_chain_diagnostics.csv", index=False
)
frequency.to_csv(
    OUTPUT / "nc_seat_frequencies_all.csv"
)
post_frequency.to_csv(
    OUTPUT / "nc_seat_frequencies_post500.csv"
)

print("\nPER-CHAIN DIAGNOSTICS")
print(summary.round(4).to_string(index=False))

print(f"\nALL {len(combined):,} STATES")
print(f"Total states: {len(combined)}")
print(f"Unique plan hashes: {unique_total}")
print(f"Repeated state hashes: {len(combined) - unique_total}")
print(f"Plan hashes shared across chains: {shared_across_chains}")
print(f"Combined mean seats: {combined.dem_seats.mean():.4f}")

print("\nSEAT DISTRIBUTION - ALL STATES")
print(frequency.to_string())

print("\nSEAT DISTRIBUTION - AFTER FIRST 500 PER CHAIN")
print(post_frequency.to_string())
print(f"Post-warmup states: {len(post500)}")
print(f"Post-warmup mean seats: {post500.dem_seats.mean():.4f}")

print(f"\nProvisional split-Rhat (seat count): {rhat:.4f}")
print("Note: correlated, discrete seat counts require cautious interpretation.")
print("Multiple chains and Rhat alone do not establish representative sampling.")
print("\nNC multi-chain analysis completed")


