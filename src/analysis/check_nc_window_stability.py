"""Check stability of NC ReCom metrics across consecutive windows."""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "outputs/ensembles"

SEEDS = [101, 202, 303]
EXPECTED_STEPS = 2000
WINDOW = 250

REQUIRED = [
    "step", "seed", "dem_seats",
    "efficiency_gap", "cut_edges", "plan_hash"
]

for seed in SEEDS:
    files = sorted(SOURCE.glob(
        f"north_carolina_chain_eps0p01_seed{seed}_steps*.csv"
    ))

    if not files:
        raise FileNotFoundError(f"No data for seed {seed}")

    frames = []

    for path in files:
        frame = pd.read_csv(path)

        if not set(REQUIRED).issubset(frame.columns):
            raise ValueError(f"Missing columns: {path.name}")

        if not (frame["seed"] == seed).all():
            raise ValueError(f"Wrong seed in {path.name}")

        frames.append(frame)

    data = (
        pd.concat(frames, ignore_index=True)
        .sort_values("step")
        .reset_index(drop=True)
    )

    if data.step.tolist() != list(range(EXPECTED_STEPS)):
        raise ValueError(
            f"Missing or duplicate steps for seed {seed}"
        )

    if data[REQUIRED].isna().any().any():
        raise ValueError(f"Missing values for seed {seed}")

    data["window_start"] = (
        data["step"] // WINDOW
    ) * WINDOW

    summary = data.groupby("window_start").agg(
        mean_seats=("dem_seats", "mean"),
        mean_eff_gap=("efficiency_gap", "mean"),
        mean_cut_edges=("cut_edges", "mean"),
        seats_le3=(
            "dem_seats",
            lambda values: int((values <= 3).sum())
        ),
        unique_plans=("plan_hash", "nunique"),
    )

    summary["window_end"] = summary.index + WINDOW - 1

    summary = summary[
        [
            "window_end", "mean_seats",
            "mean_eff_gap", "mean_cut_edges",
            "seats_le3", "unique_plans"
        ]
    ]

    print(f"\nSEED {seed}")
    print("=" * 70)
    print(summary.round(4).to_string())

    first = summary.iloc[0]
    last = summary.iloc[-1]

    print(
        f"\nFirst-to-last mean seat difference: "
        f"{last.mean_seats - first.mean_seats:+.3f}"
    )

    print(
        f"First-to-last mean cut-edge difference: "
        f"{last.mean_cut_edges - first.mean_cut_edges:+.2f}"
    )

print("\nWindow stability audit completed")
print("Stable window means alone do not establish convergence.")
