"""Checkpoint provenance and protected segment preflight, independent of GIS imports."""

import hashlib
from importlib import metadata
import json
from pathlib import Path
import platform
import re
import sys


class CanonicalEdgeSet(set):
    """Keep set operations while giving random-choice inputs stable iteration.

    Reordering a uniformly sampled finite edge set preserves its selection
    probabilities, but changes seeded trajectories. Legacy runs remain separate.
    """

    def __iter__(self):
        return iter(sorted(set.__iter__(self)))


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def provenance(args, graph, runner):
    attributes = (args.assignment_col, args.population_col, args.dem_col, args.rep_col)
    nodes = [(str(node), {column: str(graph.nodes[node][column]) for column in attributes})
             for node in graph.nodes]
    edges = sorted(tuple(sorted((str(left), str(right)))) for left, right in graph.edges)
    payload = json.dumps({"nodes": sorted(nodes), "edges": edges}, sort_keys=True).encode()
    packages = {}
    for package in ("gerrychain", "networkx", "geopandas", "shapely", "pandas", "numpy", "pyproj"):
        packages[package] = metadata.version(package)
    return {
        "dataset_sha256": file_sha256(args.dataset),
        "graph_sha256": hashlib.sha256(payload).hexdigest(),
        "runner_sha256": file_sha256(runner),
        "checkpoint_code_sha256": file_sha256(__file__),
        "runtime": {"python": sys.version, "platform": platform.platform(), "packages": packages},
        "configuration": {key: getattr(args, key) for key in (
            "state", "layer", "assignment_col", "population_col", "dem_col", "rep_col",
            "epsilon", "node_repeats", "sample_every",
        )},
    }


def validate_checkpoint(checkpoint, expected, seed):
    if checkpoint.get("version") != 2:
        raise ValueError("Legacy checkpoint provenance is unverifiable; refusing continuation")
    if checkpoint.get("seed") != seed:
        raise ValueError("Checkpoint seed mismatch")
    if not isinstance(checkpoint.get("next_step"), int) or checkpoint["next_step"] < 1:
        raise ValueError("Invalid checkpoint next_step")
    actual = checkpoint.get("provenance", {})
    for key, value in expected.items():
        if actual.get(key) != value:
            raise ValueError(f"Checkpoint compatibility mismatch: {key}")


def protect_run(output_dir, checkpoint_dir, slug, epsilon, seed, start, steps):
    tag = f"{epsilon:g}".replace(".", "p")
    prefix = f"{slug}_chain_eps{tag}_seed{seed}_steps"
    last = start + steps - 1
    for path in Path(output_dir).glob(prefix + "*.csv"):
        match = re.fullmatch(re.escape(prefix) + r"(\d+)-(\d+)\.csv", path.name)
        if not match:
            raise ValueError(f"Unrecognized existing segment: {path.name}")
        first_existing, last_existing = map(int, match.groups())
        if max(start, first_existing) <= min(last, last_existing):
            raise FileExistsError(f"Refusing overlapping chain segment: {path}")
    checkpoints = set(range(((start // 100) + 1) * 100, start + steps + 1, 100))
    checkpoints.add(start + steps)
    for next_step in checkpoints:
        path = Path(checkpoint_dir) / f"{slug}_checkpoint_eps{tag}_seed{seed}_next{next_step}.pkl"
        if path.exists():
            raise FileExistsError(f"Refusing existing checkpoint: {path}")
