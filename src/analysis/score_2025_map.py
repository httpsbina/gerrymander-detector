"""
score_2025_map.py
takes the 2025 enacted congressional plan (PLANC2333) and figures out
how many dem seats it would produce using the same 2024 presidential
vote data, then compares it to our ensemble
"""

import os
import geopandas as gpd
import pandas as pd

root = os.path.join(os.path.expanduser("~"), "OneDrive", "Documents", "gerrymander-detector")

print("loading merged precinct data...")
precincts = gpd.read_file(os.path.join(root, "data", "processed", "tx_merged.shp"))

print("loading 2025 congressional plan...")
plan2025 = gpd.read_file(os.path.join(root, "data", "raw", "shapefiles", "PLANC2333", "PLANC2333.shp"))
plan2025 = plan2025.to_crs(precincts.crs)

print("assigning precincts to 2025 districts by centroid...")
centroids = precincts.copy()
centroids["geometry"] = centroids.geometry.centroid

joined = gpd.sjoin(centroids, plan2025[["District", "geometry"]], how="left", predicate="within")

precincts["CONG_2025"] = joined["District"]

unmatched = precincts["CONG_2025"].isna().sum()
if unmatched > 0:
    print(f"  {unmatched} precincts didnt fall in any 2025 district, dropping them")
    precincts = precincts.dropna(subset=["CONG_2025"])

print("\n2025 map results (using 2024 presidential vote):")
by_district = precincts.groupby("CONG_2025").agg(
    dem=("G24PREDHAR", "sum"),
    rep=("G24PRERTRU", "sum"),
    pop=("TOTPOP", "sum"),
).reset_index()

by_district["dem_pct"] = by_district["dem"] / (by_district["dem"] + by_district["rep"])
by_district["winner"] = by_district["dem_pct"].apply(lambda x: "D" if x > 0.5 else "R")

dem_seats_2025 = (by_district["winner"] == "D").sum()
rep_seats_2025 = (by_district["winner"] == "R").sum()

print(f"  dem seats: {dem_seats_2025}")
print(f"  rep seats: {rep_seats_2025}")

print("\ndistrict-by-district breakdown:")
by_district = by_district.sort_values("dem_pct", ascending=False)
for _, row in by_district.iterrows():
    marker = "<<<" if row["winner"] == "D" else ""
print(f"  district {int(row['CONG_2025']):>4d}: {row['dem_pct']:.1%} Dem  {marker}")
print("\ncomparing to ensemble...")
csv_path = os.path.join(root, "outputs", "ensembles", "tx_test_5000steps.csv")
ensemble = pd.read_csv(csv_path)

percentile = (ensemble["dem_seats"] <= dem_seats_2025).mean() * 100
print(f"  2025 enacted map: {dem_seats_2025} dem seats")
print(f"  ensemble range: {ensemble['dem_seats'].min()} - {ensemble['dem_seats'].max()}")
print(f"  ensemble mean: {ensemble['dem_seats'].mean():.1f}")
print(f"  percentile rank of 2025 map: {percentile:.1f}%")

if percentile < 5 or percentile > 95:
    print("  ** this map is a statistical outlier **")
else:
    print("  this map falls within the normal range (need more samples to be sure)")

print("done!")