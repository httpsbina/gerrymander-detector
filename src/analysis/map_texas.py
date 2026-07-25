"""
map_texas.py
draws texas congressional districts side by side
old (2021) vs new (2025) colored by partisan lean
"""

import os
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors

root = os.path.join(os.path.expanduser("~"), "OneDrive", "Documents", "gerrymander-detector")

print("loading data...")
precincts = gpd.read_file(os.path.join(root, "data", "processed", "tx_merged.shp"))

plan2025 = gpd.read_file(os.path.join(root, "data", "raw", "shapefiles", "PLANC2333", "PLANC2333.shp"))
plan2025 = plan2025.to_crs(precincts.crs)

centroids = precincts.copy()
centroids["geometry"] = centroids.geometry.centroid
joined = gpd.sjoin(centroids, plan2025[["District", "geometry"]], how="left", predicate="within")
precincts["CONG_2025"] = joined["District"]

print("dissolving districts...")
old_districts = precincts.dissolve(by="CONG_DIST", aggfunc="sum")
old_districts["dem_pct"] = old_districts["G24PREDHAR"] / (old_districts["G24PREDHAR"] + old_districts["G24PRERTRU"])

precincts_2025 = precincts.dropna(subset=["CONG_2025"]).copy()
new_districts = precincts_2025.dissolve(by="CONG_2025", aggfunc="sum")
new_districts["dem_pct"] = new_districts["G24PREDHAR"] / (new_districts["G24PREDHAR"] + new_districts["G24PRERTRU"])

cmap = mcolors.LinearSegmentedColormap.from_list("partisan", ["#b22234", "#f0f0f0", "#3c3b6e"])
norm = mcolors.Normalize(vmin=0.25, vmax=0.75)

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(18, 9))

old_districts.plot(column="dem_pct", cmap=cmap, norm=norm, ax=ax1, edgecolor="black", linewidth=0.5)
old_dem = (old_districts["dem_pct"] > 0.5).sum()
old_rep = (old_districts["dem_pct"] <= 0.5).sum()
ax1.set_title(f"2021 Congressional Map\n({old_dem} Dem / {old_rep} Rep seats)", fontsize=14)
ax1.axis("off")

new_districts.plot(column="dem_pct", cmap=cmap, norm=norm, ax=ax2, edgecolor="black", linewidth=0.5)
new_dem = (new_districts["dem_pct"] > 0.5).sum()
new_rep = (new_districts["dem_pct"] <= 0.5).sum()
ax2.set_title(f"2025 Congressional Map\n({new_dem} Dem / {new_rep} Rep seats)", fontsize=14)
ax2.axis("off")

sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
cbar = fig.colorbar(sm, ax=[ax1, ax2], orientation="horizontal", fraction=0.04, pad=0.08, shrink=0.6)
cbar.set_label("Democratic two-party vote share", fontsize=12)
cbar.set_ticks([0.3, 0.4, 0.5, 0.6, 0.7])
cbar.set_ticklabels(["30%", "40%", "50%", "60%", "70%"])

fig.suptitle("Texas Congressional Redistricting: 2021 vs 2025", fontsize=16, fontweight="bold", y=0.98)
plt.tight_layout(rect=[0, 0.08, 1, 0.95])

plot_path = os.path.join(root, "outputs", "figures", "tx_district_maps.png")
plt.savefig(plot_path, dpi=150, bbox_inches="tight")
print(f"saved to {plot_path}")

plt.show()