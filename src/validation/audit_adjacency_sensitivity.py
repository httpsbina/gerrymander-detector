"""Compare GerryChain adjacency with exact positive shared-boundary adjacency."""

import argparse
import hashlib
import json
from pathlib import Path
import warnings

import geopandas as gpd
from gerrychain import Graph
import networkx as nx

ROOT = Path(__file__).resolve().parents[2]


def edge_set(graph):
    return {tuple(sorted((int(left), int(right)))) for left, right in graph.edges}


def compare(frame):
    frame = frame.reset_index(drop=True)
    if not frame.geometry.is_valid.all() or frame.geometry.is_empty.any():
        raise ValueError("Adjacency comparison requires valid nonempty candidate geometry")
    if not frame.crs.is_projected:
        raise ValueError("Projected CRS required")
    metres = float(frame.crs.axis_info[0].unit_conversion_factor)
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        sampler = Graph.from_geodataframe(frame, adjacency="rook", cols_to_add=["UNIQUE_ID"])
    boundary = nx.Graph()
    boundary.add_nodes_from(range(len(frame)))
    pairs = frame.sindex.query(frame.geometry, predicate="intersects")
    for left, right in zip(*pairs):
        if left < right and frame.geometry.iloc[left].boundary.intersection(frame.geometry.iloc[right].boundary).length > 0:
            boundary.add_edge(int(left), int(right))
    sampler_edges, boundary_edges = edge_set(sampler), edge_set(boundary)
    rows = []
    for category, edges in (("sampler_only", sampler_edges - boundary_edges),
                            ("boundary_only", boundary_edges - sampler_edges)):
        for left, right in sorted(edges):
            a, b = frame.geometry.iloc[left], frame.geometry.iloc[right]
            rows.append({
                "category": category, "left": str(frame.UNIQUE_ID.iloc[left]),
                "right": str(frame.UNIQUE_ID.iloc[right]),
                "intersection_area_m2": a.intersection(b).area * metres ** 2,
                "intersection_length_m": a.intersection(b).length * metres,
                "shared_boundary_length_m": a.boundary.intersection(b.boundary).length * metres,
                "distance_m": a.distance(b) * metres,
            })
    def digest(edges):
        labels = sorted(tuple(sorted((str(frame.UNIQUE_ID.iloc[a]), str(frame.UNIQUE_ID.iloc[b]))))
                        for a, b in edges)
        return hashlib.sha256(json.dumps(labels, separators=(",", ":")).encode()).hexdigest()
    return {"research_ready": False, "nodes": len(frame), "sampler_edges": len(sampler_edges),
            "boundary_edges": len(boundary_edges), "sampler_components": nx.number_connected_components(sampler),
            "boundary_components": nx.number_connected_components(boundary),
            "sampler_edge_sha256": digest(sampler_edges), "boundary_edge_sha256": digest(boundary_edges),
            "differences": rows, "warnings": [str(warning.message) for warning in captured],
            "interpretation": "Neither graph is substituted for the configured sampler; discrepancies require methodological review"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    for path in (args.dataset, args.output):
        path.resolve().relative_to(ROOT)
    if args.output.exists():
        raise FileExistsError("Refusing existing adjacency report")
    frame = gpd.read_file(args.dataset, layer="precincts")
    report = compare(frame)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({key: value for key, value in report.items() if key != "warnings"}, indent=2))


if __name__ == "__main__":
    main()
