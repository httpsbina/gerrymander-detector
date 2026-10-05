from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]

ANALYSIS = ROOT / "outputs" / "analysis"
FIGURES = ROOT / "outputs" / "figures"

FIGURES.mkdir(parents=True, exist_ok=True)

ensemble = pd.read_csv(
    ANALYSIS / "texas_post_burnin_states.csv"
)


# ============================================================
# FINAL COMPARISON TABLE
# ============================================================

benchmarks = [
    {
        "plan": "Current Texas map",
        "dem_seats": 11,
        "efficiency_gap": -0.130938,
        "mean_median": -0.057243,
        "max_pop_dev_pct": 0.052416,
    },
    {
        "plan": "Representative neutral (step 26999)",
        "dem_seats": 13,
        "efficiency_gap": -0.049588,
        "mean_median": 0.008427,
        "max_pop_dev_pct": 0.098043,
    },
    {
        "plan": "PLANC2333 (2025)",
        "dem_seats": 8,
        "efficiency_gap": -0.193900,
        "mean_median": -0.052861,
        "max_pop_dev_pct": 0.00012695,
    },
]

rows = []

for b in benchmarks:
    row = dict(b)

    row["seat_lower_tail_pct"] = (
        ensemble["dem_seats"] <= b["dem_seats"]
    ).mean() * 100

    row["eff_gap_lower_tail_pct"] = (
        ensemble["efficiency_gap"]
        <= b["efficiency_gap"]
    ).mean() * 100

    row["mean_median_lower_tail_pct"] = (
        ensemble["mean_median"]
        <= b["mean_median"]
    ).mean() * 100

    rows.append(row)

comparison = pd.DataFrame(rows)

comparison_path = (
    ANALYSIS / "texas_final_map_comparison.csv"
)

comparison.to_csv(
    comparison_path,
    index=False,
)

print("Final map comparison")
print("====================")
print(
    comparison.to_string(
        index=False,
        float_format=lambda x: f"{x:.6f}",
    )
)


# ============================================================
# SEAT DISTRIBUTION
# ============================================================

fig, ax = plt.subplots(figsize=(8, 5))

bins = np.arange(7.5, 18.5, 1)

ax.hist(
    ensemble["dem_seats"],
    bins=bins,
)

ax.axvline(
    11,
    linestyle="--",
    linewidth=2,
    label="Current map: 11",
)

ax.axvline(
    13,
    linestyle=":",
    linewidth=2,
    label="Representative neutral: 13",
)

ax.axvline(
    8,
    linestyle="-.",
    linewidth=2,
    label="PLANC2333: 8",
)

ax.set_xlabel(
    "Harris-won congressional districts"
)

ax.set_ylabel(
    "Observed ensemble states"
)

ax.set_title(
    "Texas Neutral Ensemble: Democratic Seat Distribution"
)

ax.legend()

seat_fig = (
    FIGURES / "texas_dem_seat_distribution.png"
)

fig.savefig(
    seat_fig,
    dpi=200,
    bbox_inches="tight",
)

plt.close(fig)


# ============================================================
# EFFICIENCY GAP
# ============================================================

fig, ax = plt.subplots(figsize=(8, 5))

ax.hist(
    ensemble["efficiency_gap"],
    bins=50,
)

ax.axvline(
    -0.130938,
    linestyle="--",
    linewidth=2,
    label="Current map",
)

ax.axvline(
    -0.049588,
    linestyle=":",
    linewidth=2,
    label="Representative neutral",
)

ax.axvline(
    -0.193900,
    linestyle="-.",
    linewidth=2,
    label="PLANC2333",
)

ax.set_xlabel(
    "Efficiency gap"
)

ax.set_ylabel(
    "Observed ensemble states"
)

ax.set_title(
    "Texas Neutral Ensemble: Efficiency Gap"
)

ax.legend()

eg_fig = (
    FIGURES / "texas_efficiency_gap_distribution.png"
)

fig.savefig(
    eg_fig,
    dpi=200,
    bbox_inches="tight",
)

plt.close(fig)


# ============================================================
# MEAN-MEDIAN
# ============================================================

fig, ax = plt.subplots(figsize=(8, 5))

ax.hist(
    ensemble["mean_median"],
    bins=50,
)

ax.axvline(
    -0.057243,
    linestyle="--",
    linewidth=2,
    label="Current map",
)

ax.axvline(
    0.008427,
    linestyle=":",
    linewidth=2,
    label="Representative neutral",
)

ax.axvline(
    -0.052861,
    linestyle="-.",
    linewidth=2,
    label="PLANC2333",
)

ax.set_xlabel(
    "Mean-median difference"
)

ax.set_ylabel(
    "Observed ensemble states"
)

ax.set_title(
    "Texas Neutral Ensemble: Mean-Median"
)

ax.legend()

mm_fig = (
    FIGURES / "texas_mean_median_distribution.png"
)

fig.savefig(
    mm_fig,
    dpi=200,
    bbox_inches="tight",
)

plt.close(fig)


# ============================================================
# MAPS
# ============================================================

precincts = gpd.read_file(
    ROOT
    / "data"
    / "processed"
    / "tx_precincts_validated.gpkg",
    layer="precincts",
)

neutral = gpd.read_file(
    ANALYSIS
    / "texas_representative_neutral_plan.gpkg",
    layer="representative_neutral",
)

plan2025 = gpd.read_file(
    ROOT
    / "data"
    / "raw"
    / "shapefiles"
    / "PLANC2333"
    / "PLANC2333.shp"
)

if plan2025.crs != precincts.crs:
    plan2025 = plan2025.to_crs(
        precincts.crs
    )


def save_map(boundaries, title, filename):
    fig, ax = plt.subplots(figsize=(9, 8))

    boundaries.boundary.plot(
        ax=ax,
        linewidth=0.8,
    )

    ax.set_title(title)
    ax.set_axis_off()

    fig.savefig(
        FIGURES / filename,
        dpi=200,
        bbox_inches="tight",
    )

    plt.close(fig)


current_districts = (
    precincts
    .dissolve(by="CONG_DIST")
)

neutral_districts = (
    neutral
    .dissolve(by="NEUTRAL_DIST")
)

if "District" in plan2025.columns:
    enacted_2025 = (
        plan2025
        .dissolve(by="District")
    )
else:
    enacted_2025 = plan2025


save_map(
    current_districts,
    "Current Texas Congressional Map",
    "texas_current_map.png",
)

save_map(
    neutral_districts,
    "Representative Neutral Plan — Step 26,999",
    "texas_representative_neutral_map.png",
)

save_map(
    enacted_2025,
    "Texas PLANC2333 — 2025",
    "texas_planc2333_map.png",
)


print()
print("Saved")
print("=====")
print(comparison_path)
print(seat_fig)
print(eg_fig)
print(mm_fig)
print(FIGURES / "texas_current_map.png")
print(FIGURES / "texas_representative_neutral_map.png")
print(FIGURES / "texas_planc2333_map.png")
