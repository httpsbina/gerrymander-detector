"""Validate shared NC 2023/2025 geography and rook adjacency."""

from pathlib import Path

import geopandas as gpd
import networkx as nx
import pandas as pd
from gerrychain import Graph

ROOT = Path(__file__).resolve().parents[2]
PROCESSED = ROOT / "data/processed"

SOURCE = PROCESSED / "nc_precincts_common_2023_2025.gpkg"
ORIGINAL = PROCESSED / "nc_precincts_validated.gpkg"
REFERENCE = PROCESSED / "nc_plan_comparison.csv"

METRICS = ["TOTPOP", "G24PREDHAR", "G24PRERTRU"]
TOTALS = (10_439_388, 2_713_609, 2_896_942)
SPLIT = "ONSLOW-:-SW19|03"

print("Reading common North Carolina geography...")

units = gpd.read_file(SOURCE, layer="precincts").reset_index(drop=True)

if len(units) != 2681 or not units.UNIT_ID.is_unique:
    raise ValueError("Invalid geographic unit count or IDs")

if units.crs is None:
    raise ValueError("Missing coordinate system")

if (
    units.geometry.isna().any()
    or units.geometry.is_empty.any()
    or not units.geometry.is_valid.all()
):
    raise ValueError("Invalid geographic geometry")

if units[METRICS].isna().any().any():
    raise ValueError("Missing population or election values")

if tuple(int(units[c].sum()) for c in METRICS) != TOTALS:
    raise ValueError("Statewide totals mismatch")

if int(units.BLOCK_COUNT.sum()) != 236638:
    raise ValueError("Census block coverage mismatch")

for col in ("CONG_DIST", "CONG_DIST_2025"):
    units[col] = units[col].astype(str).str.zfill(2)

    if set(units[col]) != {f"{x:02d}" for x in range(1, 15)}:
        raise ValueError(f"Invalid district assignments: {col}")

print("Checking Onslow split geometry...")

previous = gpd.read_file(ORIGINAL, layer="precincts")
original = previous.loc[
    previous.UNIT_ID == SPLIT, "geometry"
]

if len(original) != 1:
    raise ValueError("Original Onslow unit not found")

parts = units.loc[
    units.UNIT_ID.isin([
        SPLIT + "|25-01",
        SPLIT + "|25-03"
    ])
]

if len(parts) != 2:
    raise ValueError("Expected two Onslow pieces")

if sorted(parts.TOTPOP.tolist()) != [2597, 4853]:
    raise ValueError("Incorrect Onslow population split")

piece_a, piece_b = parts.geometry.tolist()

if piece_a.intersection(piece_b).area > 1:
    raise ValueError("Onslow pieces overlap substantially")

recombined = piece_a.union(piece_b)
difference = original.iloc[0].symmetric_difference(recombined).area

print(f"Onslow geometric difference: {difference:.10f} sq ft")

if difference > 1:
    raise ValueError("Onslow pieces do not preserve original geometry")

print("\nBuilding rook adjacency graph...")

graph = Graph.from_geodataframe(
    units,
    adjacency="rook",
    cols_to_add=[
        "UNIT_ID", "CONG_DIST", "CONG_DIST_2025",
        *METRICS
    ]
)

network = (
    graph.get_nx_graph()
    if hasattr(graph, "get_nx_graph")
    else graph
)

if set(network.nodes) != set(units.index):
    raise ValueError("Graph node mismatch")

components = list(nx.connected_components(network))
isolates = list(nx.isolates(network))

print(f"Nodes: {network.number_of_nodes():,}")
print(f"Edges: {network.number_of_edges():,}")
print(f"Connected components: {len(components)}")
print(f"Isolated units: {len(isolates)}")

for metric in METRICS:
    actual = sum(
        int(data[metric])
        for _, data in network.nodes(data=True)
    )
    if actual != int(units[metric].sum()):
        raise ValueError(f"Graph attribute mismatch: {metric}")

reference = pd.read_csv(REFERENCE)
ideal = TOTALS[0] / 14

disconnected = []

for year, column in [
    (2023, "CONG_DIST"),
    (2025, "CONG_DIST_2025")
]:
    expected = (
        reference.loc[reference.plan_year == year]
        .set_index("district")
    )

    print(f"\n{year} CONGRESSIONAL DISTRICTS")
    print("=" * 65)

    for district in range(1, 15):
        code = f"{district:02d}"
        nodes = units.index[units[column] == code].tolist()

        if not nodes:
            raise ValueError(f"Empty district {year}/{code}")

        subgraph = network.subgraph(nodes)
        count = nx.number_connected_components(subgraph)

        totals = units.loc[
            units[column] == code, METRICS
        ].sum()

        for metric, expected_col in [
            ("TOTPOP", "population"),
            ("G24PREDHAR", "harris_votes"),
            ("G24PRERTRU", "trump_votes")
        ]:
            if int(totals[metric]) != int(
                expected.loc[district, expected_col]
            ):
                raise ValueError(
                    f"{year} district {code} {metric} mismatch"
                )

        pop = int(totals.TOTPOP)
        deviation = 100 * (pop / ideal - 1)

        print(
            f"District {code}: "
            f"{len(nodes):3d} units, "
            f"{count} component(s), "
            f"population {pop:,}, "
            f"deviation {deviation:+.6f}%"
        )

        if count != 1:
            disconnected.append((year, code, count))

    print(f"{year}: district totals validated")

print("\nFINAL RESULTS")
print(f"Disconnected districts: {disconnected}")
print(f"Graph components: {len(components)}")
print(f"Graph isolates: {len(isolates)}")

if len(components) != 1 or isolates or disconnected:
    raise RuntimeError("Common NC graph validation failed")

print("\nNC common graph validation passed")
