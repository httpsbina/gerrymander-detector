"""
build_texas_dataset.py
merges election results with census population so we have everything
in one file for gerrychain

had to use centroid spatial join instead of maup.assign because
maup was taking forever on 10k polygons

the election file has 9712 precincts but census only has 9007 VTDs
because boundaries shifted between 2020 and 2024. centroid matching
isnt perfect but its close enough for redistricting analysis
"""

import geopandas as gpd
import warnings
import os

warnings.filterwarnings("ignore")

root = os.path.join(os.path.expanduser("~"), "OneDrive", "Documents", "gerrymander-detector")

print("loading election data...")
elec = gpd.read_file(os.path.join(root, "data", "raw", "election_results",
    "tx_2024_gen_cong_tx_vtd", "tx_2024_gen_cong_tx_vtd.shp"))
print(f"  got {len(elec)} precincts")

print("grabbing presidential vote totals from statewide file...")
allraces = gpd.read_file(os.path.join(root, "data", "raw", "election_results",
    "tx_2024_gen_all_tx_vtd", "tx_2024_gen_all_tx_vtd.shp"))

elec["G24PREDHAR"] = allraces["G24PREDHAR"]
elec["G24PRERTRU"] = allraces["G24PRERTRU"]
if "County" not in elec.columns:
    elec["County"] = allraces["County"]

print("loading census population...")
census = gpd.read_file(os.path.join(root, "data", "raw", "shapefiles",
    "tx_pl2020_vtd", "tx_pl2020_vtd.shp"))
print(f"  got {len(census)} census VTDs")

census_pop = census[["P0010001", "P0030001", "geometry"]].copy()
census_pop = census_pop.to_crs(elec.crs)

print("matching census VTDs to election precincts by centroid...")
centroids = census_pop.copy()
centroids["geometry"] = centroids.geometry.centroid

matched = gpd.sjoin(centroids, elec[["geometry"]], how="left", predicate="within")

pop_by_precinct = matched.groupby("index_right").agg({
    "P0010001": "sum",
    "P0030001": "sum"
})
pop_by_precinct.columns = ["TOTPOP", "VAP"]

elec = elec.join(pop_by_precinct)

missing = elec["TOTPOP"].isna().sum()
if missing > 0:
    print(f"  {missing} precincts didnt match any census VTD, setting pop to 0")
    elec["TOTPOP"] = elec["TOTPOP"].fillna(0)
    elec["VAP"] = elec["VAP"].fillna(0)

elec["TOTPOP"] = elec["TOTPOP"].astype(int)
elec["VAP"] = elec["VAP"].astype(int)

total_pop = elec["TOTPOP"].sum()
num_dists = elec["CONG_DIST"].nunique()
ideal = total_pop / num_dists
print(f"  total pop: {total_pop:,.0f}")
print(f"  {num_dists} districts, ideal pop per district: {ideal:,.0f}")

zeros = (elec["TOTPOP"] == 0).sum()
if zeros > 0:
    print(f"  {zeros} precincts with zero pop (probably water or empty areas)")

keep = ["UNIQUE_ID", "COUNTYFP", "County", "TX_VTD", "CONG_DIST",
        "TOTPOP", "VAP", "G24PREDHAR", "G24PRERTRU", "geometry"]
final = elec[[c for c in keep if c in elec.columns]].copy()

output_path = os.path.join(root, "data", "processed", "tx_merged.shp")
final.to_file(output_path)
print(f"\nsaved to {output_path}")
print(f"  {len(final)} precincts, {len(final.columns)} columns")

dem = final["G24PREDHAR"].sum()
rep = final["G24PRERTRU"].sum()
print(f"\n  harris: {dem:,.0f}")
print(f"  trump:  {rep:,.0f}")
print(f"  two-party dem share: {dem/(dem+rep):.1%}")
print("\ndone!")