"""Generate North Carolina research figures from saved analysis tables."""

from pathlib import Path
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "outputs/analysis"
OUTPUT = SOURCE / "nc_figures"

windows = pd.read_csv(
    SOURCE / "nc_common_window_summary.csv"
)

swings = pd.read_csv(
    SOURCE / "nc_vote_swing_sensitivity.csv"
)

if len(windows) != 30:
    raise ValueError("Expected 30 chain windows")

if len(swings) != 14:
    raise ValueError("Expected 14 vote-swing scenarios")

if windows.duplicated([
    "starting_map", "seed", "window_start"
]).any():
    raise ValueError("Duplicate chain windows")

if swings.duplicated([
    "starting_map", "harris_swing_pp"
]).any():
    raise ValueError("Duplicate swing scenarios")

OUTPUT.mkdir(parents=True, exist_ok=True)

for year in (2023, 2025):
    fig, ax = plt.subplots(figsize=(9, 5))

    for seed in (707, 808, 909):
        part = windows[
            (windows.starting_map == year)
            & (windows.seed == seed)
        ].sort_values("window_start")

        if part.window_start.tolist() != list(
            range(0, 5000, 1000)
        ):
            raise ValueError(
                f"Missing windows: {year}, seed {seed}"
            )

        ax.plot(
            part.window_start + 500,
            part.mean_seats,
            marker="o",
            label=f"Seed {seed}"
        )

    ax.axhline(
        3,
        color="gray",
        linestyle="--",
        label="Enacted map: 3 seats"
    )

    ax.set_title(
        f"North Carolina ReCom: {year} Starting Map"
    )

    ax.set_xlabel(
        "Simulation step (1,000-state window midpoint)"
    )

    ax.set_ylabel("Mean Harris-won districts")
    ax.legend()
    ax.grid(alpha=0.25)

    fig.tight_layout()

    fig.savefig(
        OUTPUT / f"nc_{year}_chain_windows.png",
        dpi=200
    )

    plt.close(fig)

fig, ax = plt.subplots(figsize=(9, 5))

for year in (2023, 2025):
    part = swings[
        swings.starting_map == year
    ].sort_values("harris_swing_pp")

    if part.harris_swing_pp.tolist() != list(
        range(-3, 4)
    ):
        raise ValueError(f"Missing swing scenarios: {year}")

    ax.plot(
        part.harris_swing_pp,
        part.harris_seats,
        marker="o",
        label=f"{year} enacted map"
    )

ax.set_title(
    "North Carolina: Hypothetical Uniform Vote Swing"
)

ax.set_xlabel(
    "Harris two-party vote-share swing (percentage points)"
)

ax.set_ylabel("Harris-won congressional districts")
ax.set_xticks(range(-3, 4))
ax.legend()
ax.grid(alpha=0.25)

fig.tight_layout()

fig.savefig(
    OUTPUT / "nc_vote_swing.png",
    dpi=200
)

plt.close(fig)

print("\nNC RESEARCH FIGURES GENERATED")
print("=" * 60)

for path in sorted(OUTPUT.glob("*.png")):
    print(path)

if len(list(OUTPUT.glob("*.png"))) != 3:
    raise ValueError("Expected exactly three figures")

print("\nAll figure checks passed.")
print("Convergence limitations remain unresolved.")
