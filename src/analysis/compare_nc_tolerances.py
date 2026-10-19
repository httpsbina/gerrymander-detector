"""Compare North Carolina ReCom convergence at two population tolerances."""

import re
from pathlib import Path

import arviz as az
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "outputs/ensembles"
OUTPUT = ROOT / "outputs/analysis/nc_tolerance_diagnostics.csv"

EXPERIMENTS = [
    ("1.0%", "eps0p01", 0.01, [101, 202, 303]),
    ("0.5%", "eps0p005", 0.005, [404, 505, 606]),
]

STEPS = 2000
WARMUP = 500
METRICS = ["dem_seats", "efficiency_gap", "cut_edges"]


def scalar(result):
    if hasattr(result, "data_vars"):
        result = next(iter(result.data_vars.values()))
    return float(np.asarray(result).item())


def load_chain(tag, epsilon, seed):
    files = sorted(SOURCE.glob(
        f"north_carolina_chain_{tag}_seed{seed}_steps*.csv"
    ))

    if not files:
        raise FileNotFoundError(f"Missing files for seed {seed}")

    frames = []

    for path in files:
        match = re.search(r"steps(\d+)-(\d+)\.csv$", path.name)

        if not match:
            raise ValueError(f"Invalid filename: {path.name}")

        start, end = map(int, match.groups())
        df = pd.read_csv(path)

        required = {
            "step", "seed", "epsilon", "dem_seats",
            "efficiency_gap", "cut_edges",
            "max_abs_pop_dev", "plan_hash"
        }

        if not required.issubset(df.columns):
            raise ValueError(f"Missing columns: {path.name}")

        if df[list(required)].isna().any().any():
            raise ValueError(f"Missing data: {path.name}")

        if df.step.tolist() != list(range(start, end + 1)):
            raise ValueError(f"Invalid steps: {path.name}")

        if not (df.seed == seed).all():
            raise ValueError(f"Incorrect seed: {path.name}")

        if not np.allclose(df.epsilon, epsilon, atol=1e-10):
            raise ValueError(f"Incorrect epsilon: {path.name}")

        if (df.max_abs_pop_dev > epsilon + 1e-10).any():
            raise ValueError(f"Population violation: {path.name}")

        frames.append(df)

    chain = (
        pd.concat(frames, ignore_index=True)
        .sort_values("step")
        .reset_index(drop=True)
    )

    if chain.step.tolist() != list(range(STEPS)):
        raise ValueError(f"Incomplete chain: {seed}")

    return chain


results = []

for label, tag, epsilon, seeds in EXPERIMENTS:
    chains = {
        seed: load_chain(tag, epsilon, seed)
        for seed in seeds
    }

    combined = pd.concat(
        list(chains.values()), ignore_index=True
    )

    print(f"\nPOPULATION TOLERANCE: {label}")
    print("=" * 65)
    print(f"States: {len(combined)}")
    print(f"Unique plan hashes: {combined.plan_hash.nunique()}")

    print("\nPER-CHAIN SEAT MEANS")

    for seed in seeds:
        chain = chains[seed]
        post = chain.iloc[WARMUP:]

        print(
            f"Seed {seed}: "
            f"all={chain.dem_seats.mean():.4f}, "
            f"post-warmup={post.dem_seats.mean():.4f}, "
            f"last250={chain.iloc[-250:].dem_seats.mean():.4f}"
        )

    for metric in METRICS:
        samples = np.stack([
            chains[seed].iloc[WARMUP:][metric].to_numpy(
                dtype=float
            )
            for seed in seeds
        ])

        rhat = scalar(az.rhat(samples, method="rank"))
        bulk = scalar(az.ess(samples, method="bulk"))
        tail = scalar(az.ess(
            samples, method="tail", prob=(0.05, 0.95)
        ))

        record = {
            "tolerance": label,
            "metric": metric,
            "post_warmup_states": samples.size,
            "post_warmup_mean": samples.mean(),
            "rank_rhat": rhat,
            "bulk_ess": bulk,
            "tail_ess": tail,
        }

        results.append(record)

        print(f"\nMetric: {metric}")
        print(f"  Post-warmup mean: {samples.mean():.5f}")
        print(f"  Rank Rhat:        {rhat:.4f}")
        print(f"  Bulk ESS:         {bulk:.1f}")
        print(f"  Tail ESS:         {tail:.1f}")

    post = pd.concat([
        chains[seed].iloc[WARMUP:]
        for seed in seeds
    ])

    print("\nPOST-WARMUP SEAT DISTRIBUTION")
    print(post.dem_seats.value_counts().sort_index().to_string())

    rare = int((post.dem_seats <= 3).sum())
    print(f"\nStates with <=3 Harris seats: {rare}/{len(post)}")


OUTPUT.parent.mkdir(parents=True, exist_ok=True)
pd.DataFrame(results).to_csv(OUTPUT, index=False)

print(f"\nSaved: {OUTPUT}")
print("NC two-tolerance convergence analysis completed")
