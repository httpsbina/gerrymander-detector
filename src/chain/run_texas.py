"""
run_texas.py
builds the graph from our merged precinct shapefile and runs a
recom markov chain to generate alternative congressional maps

can pass number of steps as argument, defaults to 500 for testing
ex: python src/chain/run_texas.py 500
"""

import os
import sys
import pandas as pd
import networkx as nx
import geopandas as gpd
from gerrychain import Graph, GeographicPartition, MarkovChain, Election
from gerrychain.proposals import recom
from gerrychain.updaters import Tally, cut_edges
from gerrychain.constraints import within_percent_of_ideal_population, contiguous
from gerrychain.accept import always_accept
from functools import partial

root = os.path.join(os.path.expanduser("~"), "OneDrive", "Documents", "gerrymander-detector")
shapefile = os.path.join(root, "data", "processed", "tx_merged.shp")

print("building graph...")
gdf = gpd.read_file(shapefile)
gdf["geometry"] = gdf.geometry.buffer(0)
fixed_path = shapefile.replace("tx_merged", "tx_merged_fixed")
gdf.to_file(fixed_path)
graph = Graph.from_file(fixed_path)
print(f"  {len(graph.nodes)} nodes, {len(graph.edges)} edges")

components = list(nx.connected_components(graph))
if len(components) > 1:
    biggest = max(components, key=len)
    print(f"  graph has {len(components)} components, keeping largest ({len(biggest)} nodes)")
    graph = graph.subgraph(biggest).copy()

for node in graph.nodes:
    if graph.nodes[node]["TOTPOP"] == 0:
        graph.nodes[node]["TOTPOP"] = 1

election = Election("PRES24", {"Dem": "G24PREDHAR", "Rep": "G24PRERTRU"})

initial = GeographicPartition(
    graph,
    assignment="CONG_DIST",
    updaters={
        "population": Tally("TOTPOP", alias="population"),
        "cut_edges": cut_edges,
        "PRES24": election,
    }
)

total_pop = sum(initial["population"].values())
num_districts = len(initial)
ideal_pop = total_pop / num_districts

enacted_dem_seats = sum(1 for p in initial["PRES24"].percents("Dem") if p > 0.5)
print(f"\nenacted map:")
print(f"  pop: {total_pop:,} across {num_districts} districts (ideal: {ideal_pop:,.0f})")
print(f"  dem seats: {enacted_dem_seats}/{num_districts}")
print(f"  efficiency gap: {initial['PRES24'].efficiency_gap():.4f}")
print(f"  mean-median: {initial['PRES24'].mean_median():.4f}")

proposal = partial(recom, pop_col="TOTPOP", pop_target=ideal_pop, epsilon=0.05, node_repeats=2)
constraints = [within_percent_of_ideal_population(initial, 0.05), contiguous]

steps = int(sys.argv[1]) if len(sys.argv) > 1 else 500
print(f"\nrunning chain for {steps} steps...")

chain = MarkovChain(
    proposal=proposal,
    constraints=constraints,
    accept=always_accept,
    initial_state=initial,
    total_steps=steps,
)

results = []
for i, partition in enumerate(chain):
    if i % 10 == 0:
        dem_seats = sum(1 for p in partition["PRES24"].percents("Dem") if p > 0.5)
        results.append({
            "step": i,
            "dem_seats": dem_seats,
            "cut_edges": len(partition["cut_edges"]),
            "efficiency_gap": partition["PRES24"].efficiency_gap(),
            "mean_median": partition["PRES24"].mean_median(),
        })
    if i % 100 == 0:
        print(f"  step {i}/{steps}")

df = pd.DataFrame(results)
outpath = os.path.join(root, "outputs", "ensembles", f"tx_test_{steps}steps.csv")
df.to_csv(outpath, index=False)

print(f"\nsaved {len(df)} samples to {outpath}")
print(f"  dem seats range: {df['dem_seats'].min()} - {df['dem_seats'].max()} (mean {df['dem_seats'].mean():.1f})")
print(f"  enacted map had {enacted_dem_seats} dem seats")
print("done!")