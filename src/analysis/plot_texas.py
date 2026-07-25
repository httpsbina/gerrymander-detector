"""
plot_texas.py
plots the ensemble distribution with both the old (2021) and
new (2025) enacted maps marked
"""

import os
import pandas as pd
import matplotlib.pyplot as plt

root = os.path.join(os.path.expanduser("~"), "OneDrive", "Documents", "gerrymander-detector")

csv_path = os.path.join(root, "outputs", "ensembles", "tx_test_5000steps.csv")
df = pd.read_csv(csv_path)

enacted_old = 11
enacted_2025 = 8

fig, ax = plt.subplots(figsize=(10, 6))

ax.hist(df["dem_seats"], bins=range(df["dem_seats"].min(), df["dem_seats"].max() + 2),
        align="left", color="#4a90d9", edgecolor="black", alpha=0.8, label="ensemble")

ax.axvline(enacted_old, color="orange", linewidth=2.5, linestyle="--", label=f"2021 map ({enacted_old} Dem seats)")
ax.axvline(enacted_2025, color="red", linewidth=2.5, linestyle="--", label=f"2025 map ({enacted_2025} Dem seats)")

ax.set_xlabel("Democratic seats (out of 38)", fontsize=12)
ax.set_ylabel("number of sampled maps", fontsize=12)
ax.set_title("Texas Congressional Redistricting: Ensemble Outlier Analysis\n2024 presidential vote, 5000-step test run (n=500)", fontsize=13)
ax.legend(fontsize=11)

pct_old = (df["dem_seats"] <= enacted_old).mean() * 100
pct_2025 = (df["dem_seats"] <= enacted_2025).mean() * 100

ax.text(0.02, 0.95,
    f"2021 map: {enacted_old} seats (percentile: {pct_old:.0f}%)\n"
    f"2025 map: {enacted_2025} seats (percentile: {pct_2025:.0f}%)\n"
    f"ensemble: {df['dem_seats'].min()}-{df['dem_seats'].max()} seats (n={len(df)})",
    transform=ax.transAxes, ha="left", va="top", fontsize=10,
    bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.8))

plt.tight_layout()

plot_path = os.path.join(root, "outputs", "figures", "tx_outlier_comparison.png")
plt.savefig(plot_path, dpi=150)
print(f"saved to {plot_path}")

plt.show()