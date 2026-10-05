from pathlib import Path
import re

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

DOC_FIGURES = ROOT / "docs" / "outputs" / "figures"
DOC_FIGURES.mkdir(parents=True, exist_ok=True)

precincts = gpd.read_file(
    ROOT / "data" / "processed" / "tx_precincts_validated.gpkg",
    layer="precincts",
)

neutral = gpd.read_file(
    ANALYSIS / "texas_representative_neutral_plan.gpkg",
    layer="representative_neutral",
)

blocks = pd.read_csv(
    ROOT / "data" / "processed" / "tx_blocks_master.csv",
    low_memory=False,
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
    plan2025 = plan2025.to_crs(precincts.crs)


def district_key(value):
    if pd.isna(value):
        return None

    numbers = re.findall(r"\d+", str(value))

    if not numbers:
        return None

    return int(numbers[-1])


def dissolve_with_votes(gdf, district_col):
    plan = (
        gdf
        .dissolve(
            by=district_col,
            aggfunc={
                "G24PREDHAR": "sum",
                "G24PRERTRU": "sum",
            },
        )
        .reset_index()
    )

    plan["winner"] = np.where(
        plan["G24PREDHAR"] > plan["G24PRERTRU"],
        "Harris",
        "Trump",
    )

    return plan


current_districts = dissolve_with_votes(
    precincts,
    "CONG_DIST",
)

neutral_districts = dissolve_with_votes(
    neutral,
    "NEUTRAL_DIST",
)


# Exact block-level partisan scoring for PLANC2333.
blocks["_district_key"] = blocks["C2333"].map(
    district_key
)

block_votes = (
    blocks
    .groupby("_district_key")[
        ["G24PREDHAR", "G24PRERTRU"]
    ]
    .sum()
    .reset_index()
)

enacted_2025 = (
    plan2025
    .dissolve(by="District")
    .reset_index()
)

enacted_2025["_district_key"] = (
    enacted_2025["District"].map(district_key)
)

enacted_2025 = enacted_2025.merge(
    block_votes,
    on="_district_key",
    how="left",
    validate="one_to_one",
)

enacted_2025["winner"] = np.where(
    enacted_2025["G24PREDHAR"]
    > enacted_2025["G24PRERTRU"],
    "Harris",
    "Trump",
)


def harris_seats(plan):
    return int(
        (plan["winner"] == "Harris").sum()
    )


assert len(current_districts) == 38
assert len(neutral_districts) == 38
assert len(enacted_2025) == 38

assert harris_seats(current_districts) == 11
assert harris_seats(neutral_districts) == 13
assert harris_seats(enacted_2025) == 8


COLORS = {
    "Harris": "#2f6fbb",
    "Trump": "#c84c4c",
}


def save_partisan_map(plan, title, filename):
    fig, ax = plt.subplots(figsize=(9, 8))

    plan.plot(
        ax=ax,
        color=plan["winner"].map(COLORS),
        edgecolor="#222222",
        linewidth=0.65,
    )

    ax.set_title(title)
    ax.set_axis_off()

    legend_handles = [
        plt.Rectangle(
            (0, 0),
            1,
            1,
            facecolor=COLORS["Harris"],
            edgecolor="#222222",
            label="Harris-won district",
        ),
        plt.Rectangle(
            (0, 0),
            1,
            1,
            facecolor=COLORS["Trump"],
            edgecolor="#222222",
            label="Trump-won district",
        ),
    ]

    ax.legend(
        handles=legend_handles,
        loc="lower left",
        frameon=True,
    )

    output_path = FIGURES / filename
    docs_path = DOC_FIGURES / filename

    fig.savefig(
        output_path,
        dpi=200,
        bbox_inches="tight",
    )

    fig.savefig(
        docs_path,
        dpi=200,
        bbox_inches="tight",
    )

    plt.close(fig)


save_partisan_map(
    current_districts,
    "Current Texas Congressional Map - 11 Harris / 27 Trump",
    "texas_current_map.png",
)

save_partisan_map(
    neutral_districts,
    "Representative Neutral Plan - 13 Harris / 25 Trump",
    "texas_representative_neutral_map.png",
)

save_partisan_map(
    enacted_2025,
    "Texas PLANC2333 - 8 Harris / 30 Trump",
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

print()
print("Partisan map validation")
print("=======================")
print("Current Harris seats:", harris_seats(current_districts))
print("Neutral Harris seats:", harris_seats(neutral_districts))
print("PLANC2333 Harris seats:", harris_seats(enacted_2025))

