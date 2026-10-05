"""
analyze_thinning.py

Compare post-burn-in Markov-chain thinning intervals.

This script is state-agnostic. It reads chain CSV files produced by
the ensemble runner and compares retaining every 1st, 2nd, 3rd,
4th, 5th, and 10th state by default.
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_ENSEMBLE_DIR = (
    ROOT
    / "outputs"
    / "ensembles"
)

DEFAULT_OUTPUT_DIR = (
    ROOT
    / "outputs"
    / "analysis"
)


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Compare thinning intervals for a saved "
            "ReCom Markov chain."
        )
    )

    parser.add_argument(
        "--label",
        type=str,
        required=True,
        help="Label used for printed and saved output.",
    )

    parser.add_argument(
        "--input-pattern",
        type=str,
        required=True,
        help=(
            "Glob pattern for chain CSV segments, for example "
            "'tx_chain_eps0p001_seed101_steps*.csv'."
        ),
    )

    parser.add_argument(
        "--burn-in",
        type=int,
        default=700,
        help="Discard all global chain steps below this value.",
    )

    parser.add_argument(
        "--intervals",
        type=int,
        nargs="+",
        default=[1, 2, 3, 4, 5, 10],
        help="Thinning intervals to compare.",
    )

    parser.add_argument(
        "--ensemble-dir",
        type=Path,
        default=DEFAULT_ENSEMBLE_DIR,
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
    )

    return parser.parse_args()


def ess(values):
    """
    Autocorrelation-based effective sample size.

    Stops summing at the first non-positive autocorrelation.
    """

    x = np.asarray(values, dtype=float)

    n = len(x)

    if n < 3:
        return float(n)

    x = x - x.mean()

    var = np.dot(x, x) / n

    if var == 0:
        return float(n)

    rho_sum = 0.0

    for lag in range(1, n // 2):
        ac = (
            np.dot(
                x[:-lag],
                x[lag:],
            )
            / ((n - lag) * var)
        )

        if ac <= 0:
            break

        rho_sum += ac

    return n / (
        1.0
        + 2.0 * rho_sum
    )


def lag1(series):
    if len(series) < 3:
        return np.nan

    if series.nunique() <= 1:
        return np.nan

    return float(
        series.autocorr(lag=1)
    )


args = parse_args()

if args.burn_in < 0:
    raise ValueError(
        "--burn-in cannot be negative."
    )

if not args.intervals:
    raise ValueError(
        "At least one thinning interval is required."
    )

if any(
    interval < 1
    for interval in args.intervals
):
    raise ValueError(
        "All thinning intervals must be at least 1."
    )


ensemble_dir = (
    args.ensemble_dir.resolve()
)

output_dir = (
    args.output_dir.resolve()
)


files = sorted(
    ensemble_dir.glob(
        args.input_pattern
    )
)

if not files:
    raise FileNotFoundError(
        "No chain files matched:\n"
        f"  directory: {ensemble_dir}\n"
        f"  pattern:   {args.input_pattern}"
    )


print(
    f"{args.label} thinning diagnostics"
)

print(
    "="
    * (
        len(args.label)
        + 21
    )
)

print("\nchain files:")

for path in files:
    print(
        f"  {path.name}"
    )


parts = [
    pd.read_csv(path)
    for path in files
]

df = (
    pd.concat(
        parts,
        ignore_index=True,
    )
    .sort_values("step")
    .reset_index(drop=True)
)


required_columns = [
    "step",
    "dem_seats",
    "efficiency_gap",
    "mean_median",
    "cut_edges",
    "max_abs_pop_dev",
    "plan_hash",
]

missing_columns = [
    column
    for column in required_columns
    if column not in df.columns
]

if missing_columns:
    raise ValueError(
        "Chain CSV is missing required columns: "
        + ", ".join(missing_columns)
    )


duplicate_steps = int(
    df["step"]
    .duplicated()
    .sum()
)

if duplicate_steps:
    raise RuntimeError(
        f"Found {duplicate_steps} duplicate global steps. "
        "Do not mix overlapping chain segments."
    )


min_step = int(
    df["step"].min()
)

max_step = int(
    df["step"].max()
)

expected_steps = set(
    range(
        min_step,
        max_step + 1,
    )
)

actual_steps = set(
    df["step"]
    .astype(int)
)

missing_steps = sorted(
    expected_steps
    - actual_steps
)

if missing_steps:
    raise RuntimeError(
        "The saved chain is not contiguous. "
        "Thinning should be evaluated from a chain "
        "recorded with --sample-every 1. "
        f"Missing steps include: {missing_steps[:20]}"
    )


post = (
    df.loc[
        df["step"]
        >= args.burn_in
    ]
    .copy()
    .reset_index(drop=True)
)

if post.empty:
    raise RuntimeError(
        "No states remain after burn-in. "
        f"Maximum saved step is {max_step}."
    )


print("\nchain integrity")
print("---------------")

print(
    f"states loaded:       {len(df):,}"
)

print(
    f"global step range:   "
    f"{min_step:,} - {max_step:,}"
)

print(
    f"burn-in threshold:   "
    f"{args.burn_in:,}"
)

print(
    f"post-burn-in states: "
    f"{len(post):,}"
)

print(
    f"unique plans:        "
    f"{post['plan_hash'].nunique():,}"
)


full_mean_seats = (
    post["dem_seats"].mean()
)

full_mean_eg = (
    post["efficiency_gap"].mean()
)

full_mean_mm = (
    post["mean_median"].mean()
)


rows = []

for interval in sorted(
    set(args.intervals)
):
    thin = (
        post
        .iloc[::interval]
        .copy()
        .reset_index(drop=True)
    )

    row = {
        "interval": interval,
        "states_retained": len(thin),
        "unique_plans": (
            thin["plan_hash"]
            .nunique()
        ),
        "duplicate_states": (
            len(thin)
            - thin["plan_hash"].nunique()
        ),
        "mean_dem_seats": (
            thin["dem_seats"]
            .mean()
        ),
        "median_dem_seats": (
            thin["dem_seats"]
            .median()
        ),
        "min_dem_seats": (
            thin["dem_seats"]
            .min()
        ),
        "max_dem_seats": (
            thin["dem_seats"]
            .max()
        ),
        "mean_efficiency_gap": (
            thin["efficiency_gap"]
            .mean()
        ),
        "mean_mean_median": (
            thin["mean_median"]
            .mean()
        ),
        "mean_cut_edges": (
            thin["cut_edges"]
            .mean()
        ),
        "max_population_deviation": (
            thin["max_abs_pop_dev"]
            .max()
        ),
        "seat_lag1_acf": lag1(
            thin["dem_seats"]
        ),
        "eff_gap_lag1_acf": lag1(
            thin["efficiency_gap"]
        ),
        "mean_median_lag1_acf": lag1(
            thin["mean_median"]
        ),
        "cut_edges_lag1_acf": lag1(
            thin["cut_edges"]
        ),
        "seat_ess": ess(
            thin["dem_seats"]
        ),
        "eff_gap_ess": ess(
            thin["efficiency_gap"]
        ),
        "mean_median_ess": ess(
            thin["mean_median"]
        ),
        "cut_edges_ess": ess(
            thin["cut_edges"]
        ),
    }

    row[
        "seat_mean_delta_vs_full"
    ] = (
        row["mean_dem_seats"]
        - full_mean_seats
    )

    row[
        "eff_gap_delta_vs_full"
    ] = (
        row["mean_efficiency_gap"]
        - full_mean_eg
    )

    row[
        "mean_median_delta_vs_full"
    ] = (
        row["mean_mean_median"]
        - full_mean_mm
    )

    row[
        "seat_ess_per_retained"
    ] = (
        row["seat_ess"]
        / row["states_retained"]
    )

    row[
        "eff_gap_ess_per_retained"
    ] = (
        row["eff_gap_ess"]
        / row["states_retained"]
    )

    rows.append(row)


results = pd.DataFrame(
    rows
)


print("\nthinning comparison")
print("-------------------")

display_columns = [
    "interval",
    "states_retained",
    "unique_plans",
    "mean_dem_seats",
    "seat_lag1_acf",
    "seat_ess",
    "mean_efficiency_gap",
    "eff_gap_lag1_acf",
    "eff_gap_ess",
    "mean_mean_median",
    "mean_median_lag1_acf",
    "mean_median_ess",
]

print(
    results[
        display_columns
    ].to_string(
        index=False,
        float_format=lambda x: f"{x:.6f}",
    )
)


print("\n1/3 versus 1/4")
print("----------------")

comparison = (
    results.loc[
        results["interval"]
        .isin([3, 4])
    ]
)

if len(comparison) == 2:
    print(
        comparison[
            display_columns
        ].to_string(
            index=False,
            float_format=lambda x: f"{x:.6f}",
        )
    )
else:
    print(
        "Intervals 3 and 4 were not both requested."
    )


output_dir.mkdir(
    parents=True,
    exist_ok=True,
)

safe_label = (
    args.label
    .strip()
    .lower()
    .replace(" ", "_")
)

output_path = (
    output_dir
    / f"{safe_label}_thinning_diagnostics.csv"
)

results.to_csv(
    output_path,
    index=False,
)


print("\nsaved:")
print(
    f"  {output_path}"
)

print("\ndone!")
