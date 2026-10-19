"""Check North Carolina geographic adjacency and district contiguity."""

from pathlib import Path

import geopandas as gpd
import networkx as nx
import pandas as pd
from gerrychain import Graph

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "data/processed/nc_precincts_validated.gpkg"
COMPARISON = ROOT / "data/processed/nc_plan_comparison.csv"

METRICS = ["TOTPOP", "G24PREDHAR", "G24PRERTRU"]
EXPECTED_TOTALS = (10_439_388, 2_713_609, 2_896_942)

print("Reading NC geography...")

units = gpd.read_file(SOURCE, layer="precincts")
units = units.reset_index(drop=True)

if len(units) != 2680:
    raise ValueError(f"Unexpected unit count: {len(units)}")

if not units.UNIT_ID.is_unique:
    raise ValueError("Duplicate geographic unit IDs")

if units.geometry.isna().any() or units.geometry.is_empty.any():
    raise ValueError("Missing or empty geometry")

if not units.geometry.is_valid.all():
    raise ValueError("Invalid geometry")

if units[METRICS].isna().any().any():
    raise ValueError("Missing population or vote data")

if tuple(int(units[c].sum()) for c in METRICS) != EXPECTED_TOTALS:
    raise ValueError("Statewide totals mismatch")

units["CONG_DIST"] = units.CONG_DIST.astype(str).str.zfill(2)

districts = [f"{i:02d}" for i in range(1, 15)]

if set(units.CONG_DIST) != set(districts):
    raise ValueError("Expected 14 districts")

print("Building rook adjacency graph...")

graph = Graph.from_geodataframe(
    units,
    adjacency="rook",
    cols_to_add=[
        "UNIT_ID", "CONG_DIST",
        "TOTPOP", "G24PREDHAR", "G24PRERTRU"
    ],
)

network = (
    graph.get_nx_graph()
    if hasattr(graph, "get_nx_graph")
    else graph
)

if network.number_of_nodes() != len(units):
    raise ValueError("Graph node count mismatch")

if set(network.nodes) != set(units.index):
    raise ValueError("Graph node IDs do not match geography")

for column in METRICS:
    graph_total = sum(
        int(data[column])
        for _, data in network.nodes(data=True)
    )
    if graph_total != int(units[column].sum()):
        raise ValueError(f"Graph attributes lost: {column}")

components = sorted(
    nx.connected_components(network),
    key=len,
    reverse=True,
)

islands = list(nx.isolates(network))

print(f"\nGraph nodes: {network.number_of_nodes():,}")
print(f"Graph edges: {network.number_of_edges():,}")
print(f"Connected components: {len(components)}")
print(f"Largest component: {len(components[0]):,} units")
print(f"Isolated units: {len(islands)}")

for node in islands[:15]:
    print("  Island:", units.loc[node, "UNIT_ID"])

reference = pd.read_csv(COMPARISON)
reference = reference.loc[reference.plan_year == 2023]
reference = reference.set_index("district")

ideal_population = EXPECTED_TOTALS[0] / 14
disconnected_districts = []

print("\nDistrict contiguity and population:")

for district in districts:
    mask = units.CONG_DIST == district
    nodes = units.index[mask].tolist()
    subgraph = network.subgraph(nodes)

    count = nx.number_connected_components(subgraph)
    population = int(units.loc[mask, "TOTPOP"].sum())
    deviation = 100 * (population / ideal_population - 1)

    if population != int(reference.loc[int(district), "population"]):
        raise ValueError(f"District {district} population mismatch")

    print(
        f"District {district}: "
        f"{len(nodes)} units, "
        f"{count} component(s), "
        f"population {population:,}, "
        f"deviation {deviation:+.3f}%"
    )

    if count != 1:
        disconnected_districts.append(district)

print("\nDisconnected districts:", disconnected_districts)

if len(components) == 1 and not disconnected_districts:
    print("Rook graph and initial districts are connected")
else:
    print("Connectivity issues found; review before running ReCom")

print("NC graph audit completed")
