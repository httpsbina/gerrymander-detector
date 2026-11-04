"""Verify saved assignment fingerprints against the original geographic graph."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import pickle
from types import SimpleNamespace

import geopandas as gpd
from gerrychain import Graph

from paper.score_checkpoint_elections import sha
from src.chain.checkpoint_integrity import provenance, validate_checkpoint


def assignment_hash(assignment, edges):
    cuts = sorted(tuple(sorted((str(a), str(b)))) for a, b in edges
                  if assignment[a] != assignment[b])
    return hashlib.sha256("|".join(f"{a}:{b}" for a, b in cuts).encode()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    args = parser.parse_args()
    root = args.source_root.resolve()
    report = json.loads(args.results.read_text())
    destination = args.results.parent / "assignment_validation.json"
    if destination.exists(): raise FileExistsError(destination)
    graphs, expected, checked = {}, {}, 0
    for name, checksum in report["input_checksums"].items():
        path = root / name
        if sha(path) != checksum: raise ValueError(f"Changed input: {name}")
        if path.suffix != ".pkl": continue
        with path.open("rb") as stream: checkpoint = pickle.load(stream)
        recorded = checkpoint["provenance"]
        dataset_hash = recorded["dataset_sha256"]
        candidates = [key for key, value in report["input_checksums"].items()
                      if value == dataset_hash and key.endswith(".gpkg")]
        if len(candidates) != 1: raise ValueError("Ambiguous checkpoint dataset")
        dataset = root / candidates[0]
        if dataset_hash not in graphs:
            frame = gpd.read_file(dataset, layer=recorded["configuration"]["layer"])
            graphs[dataset_hash] = Graph.from_geodataframe(frame)
        graph = graphs[dataset_hash]
        key = json.dumps(recorded, sort_keys=True)
        if key not in expected:
            config = SimpleNamespace(**recorded["configuration"], dataset=dataset)
            expected[key] = provenance(config, graph, root / "src/chain/run_ensemble.py")
        validate_checkpoint(checkpoint, expected[key], checkpoint["seed"])
        if assignment_hash(checkpoint["assignment"], graph.edges) != checkpoint["plan_hash"]:
            raise ValueError(f"Assignment fingerprint differs: {name}")
        checked += 1
    result = {"process_nice": os.getpriority(os.PRIO_PROCESS, 0),
              "checkpoints_verified": checked, "distinct_datasets": len(graphs),
              "checks": ["input checksums", "complete checkpoint provenance", "graph identity", "assignment cut-edge fingerprint"],
              "results_sha256": sha(args.results), "validation_code_sha256": sha(__file__)}
    destination.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
