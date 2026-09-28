"""
analyze_texas_ensemble.py

Final descriptive analysis for the validated Texas congressional
redistricting ensemble.

Uses:
- checkpoint-enabled ReCom chain segments
- candidate burn-in of 700 states
- exact PLANC2333 benchmark from Census-block data

Important:
The ensemble statistics are descriptive Markov-chain frequencies.
Successive states are correlated and should not be interpreted as
independent observations.
"""

import argparse
import os
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd


ROOT = Path.home() / "OneDrive" / "Documents" / "gerrymander-detector"

ENSEMBLE_DIR = ROOT / "outputs" / "ensembles"
ANALYSIS_DIR = ROOT / "outputs" / "analysis"

BLOCK_MASTER = (
    ROOT
    / "data"
    / "processed"
    / "tx_blocks_master.csv"
)

PRECINCT_DATA = (
    ROOT
    / "data"
    / "processed"
    / "tx_precincts_validated.gpkg"
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Analyze validated Texas ReCom ensemble."
    )

    parser.add_argument(
        "--burn-in",
        type=int,
        default=700,
        help="First global chain step retained for final analysis.",
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=101,
    )

    parser.add_argument(
        "--epsilon-tag",
        type=str,
        default="0p001",
    )

    parser.add_argument(
        "--window",
        type=int,
        default=100,
        help="Window size for stability summaries.",
    )

    return parser.parse_args()


def ess(x):
    """
    Simple autocorrelation-based effective sample size estimate.

    Stops summing autocorrelation at the first non-positive lag.
    """

    x = np.asarray(x, dtype=float)

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
        1
        + 2 * rho_sum
    )


def efficiency_gap_from_district_votes(df):
    """
    Reproduce GerryChain's efficiency-gap convention exactly.

    Party 1 = Dem
    Party 2 = Rep

    GerryChain returns:
        (wasted_party2 - wasted_party1) / total_votes

    Therefore a positive value indicates an advantage
    for the first-listed party (Dem).
    """

    wasted_dem = 0.0
    wasted_rep = 0.0
    total_votes = 0.0

    for _, row in df.iterrows():
        dem = float(
            row["G24PREDHAR"]
        )

        rep = float(
            row["G24PRERTRU"]
        )

        total = (
            dem
            + rep
        )

        if total == 0:
            continue

        if dem > rep:
            wasted_dem += (
                dem
                - total / 2
            )

            wasted_rep += rep

        else:
            wasted_dem += dem

            wasted_rep += (
                rep
                - total / 2
            )

        total_votes += total

    return (
        wasted_rep
        - wasted_dem
    ) / total_votes


def mean_median_from_district_votes(df):
    totals = (
        df["G24PREDHAR"]
        + df["G24PRERTRU"]
    )

    shares = (
        df.loc[
            totals > 0,
            "G24PREDHAR",
        ]
        / totals[totals > 0]
    )

    # GerryChain convention:
    # median Democratic share - mean Democratic share.
    return (
        shares.median()
        - shares.mean()
    )


args = parse_args()

print("Texas final ensemble analysis")
print("=============================")

pattern = (
    f"tx_chain_"
    f"eps{args.epsilon_tag}_"
    f"seed{args.seed}_"
    f"steps*.csv"
)

files = sorted(
    ENSEMBLE_DIR.glob(pattern)
)

if not files:
    raise FileNotFoundError(
        f"No ensemble segment files matched: {pattern}"
    )

print("\nchain segment files:")

for path in files:
    print(f"  {path.name}")


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


# ------------------------------------------------------------
# CHAIN INTEGRITY
# ------------------------------------------------------------

print("\nchain integrity")
print("---------------")

duplicate_steps = (
    df["step"]
    .duplicated()
    .sum()
)

if duplicate_steps:
    raise RuntimeError(
        f"Found {duplicate_steps} duplicate global step IDs."
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
    df["step"].astype(int)
)

missing_steps = sorted(
    expected_steps
    - actual_steps
)

print(
    f"states loaded:       {len(df):,}"
)

print(
    f"global step range:   "
    f"{min_step:,} - {max_step:,}"
)

print(
    f"missing steps:       {len(missing_steps):,}"
)

print(
    f"duplicate step IDs:  {duplicate_steps:,}"
)

if missing_steps:
    print(
        f"first missing steps: "
        f"{missing_steps[:20]}"
    )

    raise RuntimeError(
        "Chain has missing global steps."
    )


# ------------------------------------------------------------
# VALIDATE MANUAL PARTISAN METRICS AGAINST STEP 0
# ------------------------------------------------------------

print("\nvalidating metric formulas")
print("--------------------------")

precincts = gpd.read_file(
    PRECINCT_DATA,
    layer="precincts",
)

seed_votes = (
    precincts
    .groupby("CONG_DIST")
    .agg(
        G24PREDHAR=(
            "G24PREDHAR",
            "sum",
        ),
        G24PRERTRU=(
            "G24PRERTRU",
            "sum",
        ),
    )
    .reset_index()
)

seed_eg_manual = (
    efficiency_gap_from_district_votes(
        seed_votes
    )
)

seed_mm_manual = (
    mean_median_from_district_votes(
        seed_votes
    )
)

step0 = (
    df.loc[
        df["step"] == 0
    ]
    .iloc[0]
)

print(
    f"seed EG manual:      "
    f"{seed_eg_manual:.6f}"
)

print(
    f"seed EG GerryChain:  "
    f"{step0['efficiency_gap']:.6f}"
)

print(
    f"seed MM manual:      "
    f"{seed_mm_manual:.6f}"
)

print(
    f"seed MM GerryChain:  "
    f"{step0['mean_median']:.6f}"
)

if not np.isclose(
    seed_eg_manual,
    step0["efficiency_gap"],
    atol=1e-6,
):
    raise RuntimeError(
        "Manual efficiency-gap formula does not match "
        "GerryChain."
    )

if not np.isclose(
    seed_mm_manual,
    step0["mean_median"],
    atol=1e-6,
):
    raise RuntimeError(
        "Manual mean-median formula does not match "
        "GerryChain."
    )


# ------------------------------------------------------------
# EXACT PLANC2333 BENCHMARK
# ------------------------------------------------------------

print("\nexact PLANC2333 benchmark")
print("-------------------------")

blocks = pd.read_csv(
    BLOCK_MASTER,
    low_memory=False,
)

c2333 = (
    blocks
    .groupby("C2333")
    .agg(
        TOTPOP=(
            "TOTPOP",
            "sum",
        ),
        G24PREDHAR=(
            "G24PREDHAR",
            "sum",
        ),
        G24PRERTRU=(
            "G24PRERTRU",
            "sum",
        ),
    )
    .reset_index()
)

if len(c2333) != 38:
    raise RuntimeError(
        f"Expected 38 C2333 districts, found {len(c2333)}."
    )

c2333_seats = int(
    (
        c2333["G24PREDHAR"]
        > c2333["G24PRERTRU"]
    ).sum()
)

c2333_eg = (
    efficiency_gap_from_district_votes(
        c2333
    )
)

c2333_mm = (
    mean_median_from_district_votes(
        c2333
    )
)

ideal_c2333_pop = (
    c2333["TOTPOP"].sum()
    / len(c2333)
)

c2333_max_pop_dev = (
    (
        c2333["TOTPOP"]
        / ideal_c2333_pop
        - 1
    )
    .abs()
    .max()
)

print(
    f"districts:           {len(c2333)}"
)

print(
    f"population:          "
    f"{c2333['TOTPOP'].sum():,}"
)

print(
    f"population range:    "
    f"{c2333['TOTPOP'].min():,} - "
    f"{c2333['TOTPOP'].max():,}"
)

print(
    f"max pop deviation:   "
    f"{c2333_max_pop_dev:.8%}"
)

print(
    f"Harris>Trump seats:  "
    f"{c2333_seats}/38"
)

print(
    f"efficiency gap:      "
    f"{c2333_eg:.6f}"
)

print(
    f"mean-median:         "
    f"{c2333_mm:.6f}"
)


# ------------------------------------------------------------
# FINAL ANALYSIS WINDOW
# ------------------------------------------------------------

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
        "No states remain after burn-in."
    )

print("\nanalysis window")
print("---------------")

print(
    f"burn-in removed:     "
    f"steps < {args.burn_in}"
)

print(
    f"retained steps:      "
    f"{int(post['step'].min()):,} - "
    f"{int(post['step'].max()):,}"
)

print(
    f"states retained:     "
    f"{len(post):,}"
)

unique_plans = int(
    post["plan_hash"].nunique()
)

duplicate_occurrences = (
    len(post)
    - unique_plans
)

consecutive_repeats = int(
    (
        post["plan_hash"]
        == post["plan_hash"].shift(1)
    ).sum()
)

print(
    f"unique exact plans:  "
    f"{unique_plans:,}"
)

print(
    f"duplicate states:    "
    f"{duplicate_occurrences:,}"
)

print(
    f"consecutive repeats: "
    f"{consecutive_repeats:,}"
)


# ------------------------------------------------------------
# ENSEMBLE SUMMARY
# ------------------------------------------------------------

seat_ess = ess(
    post["dem_seats"]
)

eg_ess = ess(
    post["efficiency_gap"]
)

mm_ess = ess(
    post["mean_median"]
)

cut_ess = ess(
    post["cut_edges"]
)

print("\nensemble summary")
print("----------------")

print(
    f"mean seats:          "
    f"{post['dem_seats'].mean():.3f}"
)

print(
    f"median seats:        "
    f"{post['dem_seats'].median():.1f}"
)

print(
    f"seat range:          "
    f"{post['dem_seats'].min()} - "
    f"{post['dem_seats'].max()}"
)

print(
    f"mean efficiency gap: "
    f"{post['efficiency_gap'].mean():.6f}"
)

print(
    f"mean mean-median:    "
    f"{post['mean_median'].mean():.6f}"
)

print(
    f"max population dev:  "
    f"{post['max_abs_pop_dev'].max():.6%}"
)

print(
    f"seat ESS:            "
    f"{seat_ess:.1f}"
)

print(
    f"eff-gap ESS:         "
    f"{eg_ess:.1f}"
)

print(
    f"mean-median ESS:     "
    f"{mm_ess:.1f}"
)

print(
    f"cut-edge ESS:        "
    f"{cut_ess:.1f}"
)


# ------------------------------------------------------------
# SEAT DISTRIBUTION
# ------------------------------------------------------------

seat_distribution = (
    post["dem_seats"]
    .value_counts()
    .sort_index()
    .rename_axis("dem_seats")
    .reset_index(name="states")
)

seat_distribution[
    "observed_frequency"
] = (
    seat_distribution["states"]
    / len(post)
)

print("\nobserved seat distribution")
print("--------------------------")

for _, row in seat_distribution.iterrows():
    print(
        f"{int(row['dem_seats']):2d} seats: "
        f"{int(row['states']):4d} states "
        f"({row['observed_frequency']:.2%})"
    )


# ------------------------------------------------------------
# BENCHMARK POSITION — DESCRIPTIVE ONLY
# ------------------------------------------------------------

below_benchmark = int(
    (
        post["dem_seats"]
        < c2333_seats
    ).sum()
)

equal_benchmark = int(
    (
        post["dem_seats"]
        == c2333_seats
    ).sum()
)

above_benchmark = int(
    (
        post["dem_seats"]
        > c2333_seats
    ).sum()
)

print("\nPLANC2333 vs observed ensemble")
print("------------------------------")

print(
    f"PLANC2333 seats:      "
    f"{c2333_seats}"
)

print(
    f"ensemble seat range: "
    f"{post['dem_seats'].min()} - "
    f"{post['dem_seats'].max()}"
)

print(
    f"states below:         "
    f"{below_benchmark:,}"
)

print(
    f"states equal:         "
    f"{equal_benchmark:,}"
)

print(
    f"states above:         "
    f"{above_benchmark:,}"
)


# ------------------------------------------------------------
# STABILITY WINDOWS
# ------------------------------------------------------------

post["window"] = (
    (
        post["step"]
        - args.burn_in
    )
    // args.window
)

window_summary = (
    post
    .groupby("window")
    .agg(
        start_step=(
            "step",
            "min",
        ),
        end_step=(
            "step",
            "max",
        ),
        states=(
            "step",
            "size",
        ),
        unique_plans=(
            "plan_hash",
            "nunique",
        ),
        mean_seats=(
            "dem_seats",
            "mean",
        ),
        median_seats=(
            "dem_seats",
            "median",
        ),
        min_seats=(
            "dem_seats",
            "min",
        ),
        max_seats=(
            "dem_seats",
            "max",
        ),
        mean_eff_gap=(
            "efficiency_gap",
            "mean",
        ),
        mean_mean_median=(
            "mean_median",
            "mean",
        ),
        mean_cut_edges=(
            "cut_edges",
            "mean",
        ),
        max_pop_dev=(
            "max_abs_pop_dev",
            "max",
        ),
    )
)

print(
    f"\n{args.window}-state stability windows"
)

print(
    "-" * 30
)

print(
    window_summary.to_string()
)


# ------------------------------------------------------------
# HALF-SAMPLE STABILITY
# ------------------------------------------------------------

mid = (
    len(post)
    // 2
)

first_half = (
    post.iloc[:mid]
)

second_half = (
    post.iloc[mid:]
)

print("\nfirst half vs second half")
print("-------------------------")

for metric in [
    "dem_seats",
    "efficiency_gap",
    "mean_median",
    "cut_edges",
]:
    print(
        f"{metric:18s} "
        f"first="
        f"{first_half[metric].mean(): .6f}  "
        f"second="
        f"{second_half[metric].mean(): .6f}"
    )


# ------------------------------------------------------------
# AUTOCORRELATION
# ------------------------------------------------------------

print("\nautocorrelation")
print("---------------")

for metric in [
    "dem_seats",
    "efficiency_gap",
    "mean_median",
    "cut_edges",
]:
    print(f"\n{metric}")

    for lag in [
        1,
        5,
        10,
        25,
        50,
        100,
        200,
    ]:
        if lag < len(post):
            print(
                f"  lag {lag:>3}: "
                f"{post[metric].autocorr(lag=lag): .4f}"
            )


# ------------------------------------------------------------
# BURN-IN SENSITIVITY
# ------------------------------------------------------------

print("\nburn-in sensitivity")
print("-------------------")

sensitivity_rows = []

for burn in [
    500,
    600,
    700,
    800,
    900,
]:
    subset = (
        df.loc[
            df["step"] >= burn
        ]
        .copy()
    )

    if len(subset) < 100:
        continue

    sensitivity_rows.append(
        {
            "burn_in": burn,
            "states": len(subset),
            "mean_seats": (
                subset[
                    "dem_seats"
                ].mean()
            ),
            "median_seats": (
                subset[
                    "dem_seats"
                ].median()
            ),
            "seat_ess": ess(
                subset[
                    "dem_seats"
                ]
            ),
            "mean_eff_gap": (
                subset[
                    "efficiency_gap"
                ].mean()
            ),
        }
    )

sensitivity = pd.DataFrame(
    sensitivity_rows
)

print(
    sensitivity.to_string(
        index=False
    )
)


# ------------------------------------------------------------
# SAVE ANALYSIS OUTPUTS
# ------------------------------------------------------------

ANALYSIS_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

post_path = (
    ANALYSIS_DIR
    / "texas_post_burnin_states.csv"
)

seat_path = (
    ANALYSIS_DIR
    / "texas_seat_distribution.csv"
)

window_path = (
    ANALYSIS_DIR
    / "texas_stability_windows.csv"
)

benchmark_path = (
    ANALYSIS_DIR
    / "texas_planc2333_benchmark.csv"
)

sensitivity_path = (
    ANALYSIS_DIR
    / "texas_burnin_sensitivity.csv"
)

post.to_csv(
    post_path,
    index=False,
)

seat_distribution.to_csv(
    seat_path,
    index=False,
)

window_summary.to_csv(
    window_path,
)

c2333.to_csv(
    benchmark_path,
    index=False,
)

sensitivity.to_csv(
    sensitivity_path,
    index=False,
)


summary_lines = [
    "Texas validated ensemble summary",
    "================================",
    "",
    (
        f"Analysis window: "
        f"{int(post['step'].min())}-"
        f"{int(post['step'].max())}"
    ),
    f"States retained: {len(post):,}",
    f"Unique plans: {unique_plans:,}",
    (
        f"Mean Harris>Trump districts: "
        f"{post['dem_seats'].mean():.3f}"
    ),
    (
        f"Median Harris>Trump districts: "
        f"{post['dem_seats'].median():.1f}"
    ),
    (
        f"Observed seat range: "
        f"{post['dem_seats'].min()}-"
        f"{post['dem_seats'].max()}"
    ),
    f"Seat ESS estimate: {seat_ess:.1f}",
    "",
    "PLANC2333 benchmark",
    f"Harris>Trump districts: {c2333_seats}",
    f"Efficiency gap: {c2333_eg:.6f}",
    f"Mean-median: {c2333_mm:.6f}",
    (
        f"Maximum population deviation: "
        f"{c2333_max_pop_dev:.8%}"
    ),
    "",
    (
        "Note: ensemble frequencies are "
        "descriptive Markov-chain frequencies, "
        "not independent-draw probabilities."
    ),
]

summary_path = (
    ANALYSIS_DIR
    / "texas_final_summary.txt"
)

summary_path.write_text(
    "\n".join(summary_lines),
    encoding="utf-8",
)


print("\nsaved analysis outputs")
print("----------------------")

for path in [
    summary_path,
    post_path,
    seat_path,
    window_path,
    benchmark_path,
    sensitivity_path,
]:
    print(
        f"  {path}"
    )

print("\ndone!")