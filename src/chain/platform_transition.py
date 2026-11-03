"""Preserve checkpoint state across a documented native-runtime boundary."""

import copy
import json
from pathlib import Path
import pickle
import random
from types import SimpleNamespace
import warnings

import geopandas as gpd
from gerrychain import Graph
import networkx as nx

from src.chain.benchmark_baselines import checkpoint_path
from src.chain.checkpoint_integrity import file_sha256, provenance
from src.data_prep.prepare_dispersed_texas_starts import plan_hash

ROOT = Path(__file__).resolve().parents[2]


def eligible_profile(source, target):
    """Only build/platform changes are authorized; the nominal kernel is fixed."""
    if set(source) != set(target):
        raise ValueError("Provenance fields differ")
    for field in source:
        if field != "runtime" and source[field] != target[field]:
            raise ValueError(f"Sampling input differs across transfer: {field}")
    old, new = source["runtime"], target["runtime"]
    if set(old) != {"python", "platform", "packages"} or set(new) != set(old):
        raise ValueError("Unknown runtime provenance fields")
    if old["packages"] != new["packages"]:
        raise ValueError("Scientific package versions differ")
    if old["python"].split()[0] != new["python"].split()[0]:
        raise ValueError("Python release differs; a build/platform transition alone is authorized")
    return source != target


def prepare(experiment, destination, graph_cache):
    destination = destination.resolve()
    destination.relative_to(ROOT)
    result = copy.deepcopy(experiment)
    dataset = ROOT / experiment["dataset"]
    if file_sha256(dataset) != experiment["dataset_sha256"]:
        raise ValueError("Transfer dataset differs")
    if str(dataset) not in graph_cache:
        frame = gpd.read_file(dataset, layer="precincts")
        with warnings.catch_warnings(record=True):
            graph = Graph.from_geodataframe(frame, cols_to_add=[c for c in frame.columns if c != "geometry"])
        graph_cache[str(dataset)] = graph
    graph = graph_cache[str(dataset)]
    directory = ROOT / experiment["input_dir"]
    profiles, originals = {}, {}
    for seed in experiment["seeds"]:
        final = checkpoint_path(directory.parent / "checkpoints", experiment, seed, experiment["steps"])
        with final.open("rb") as stream:
            checkpoint = pickle.load(stream)
        if checkpoint["version"] != 2 or checkpoint["seed"] != seed or checkpoint["next_step"] != experiment["steps"] or checkpoint["pythonhashseed"] != "0":
            raise ValueError("Incompatible source checkpoint")
        if any(checkpoint[name] != experiment[name] for name in ("epsilon", "node_repeats")):
            raise ValueError("Checkpoint parameters differ from the registered experiment")
        profile = checkpoint["provenance"]
        configuration = SimpleNamespace(dataset=dataset, **profile["configuration"])
        target = provenance(configuration, graph, ROOT / "src/chain/run_ensemble.py")
        eligible_profile(profile, target)
        assignment = checkpoint["assignment"]
        if set(assignment) != set(graph.nodes) or plan_hash(graph, assignment) != checkpoint["plan_hash"]:
            raise ValueError("Checkpoint assignment does not match target graph")
        population = profile["configuration"]["population_col"]
        districts = set(assignment.values())
        ideal = sum(graph.nodes[i][population] for i in graph.nodes) / experiment["districts"]
        if len(districts) != experiment["districts"]:
            raise ValueError("District count differs at transfer")
        for district in districts:
            nodes = [i for i in graph.nodes if assignment[i] == district]
            total = sum(graph.nodes[i][population] for i in nodes)
            if not nx.is_connected(graph.subgraph(nodes)) or abs(total / ideal - 1) > experiment["epsilon"] + 1e-10:
                raise ValueError("Transferred plan violates the unchanged constraints")
        random.Random().setstate(checkpoint["random_state"])
        profiles[seed] = target
        originals[seed] = final
    destination.mkdir(parents=True, exist_ok=False)
    ensembles, checkpoints = destination / "ensembles", destination / "checkpoints"
    ensembles.mkdir()
    checkpoints.mkdir()
    files = {}
    def receipt(path):
        files[str(path.relative_to(ROOT))] = file_sha256(path)
    for path in directory.glob("*.csv"):
        # The transferred workspace contains only complete, registered segments.
        import os
        (ensembles / path.name).symlink_to(os.path.relpath(path, ensembles))
        receipt(path)
    result["input_dir"] = str(ensembles.relative_to(ROOT))
    result["seed_configs"] = {}
    result["expected_checkpoint_provenance"] = {}
    records = []
    for seed in experiment["seeds"]:
        for step in (experiment["steps"] - 100, experiment["steps"]):
            source = checkpoint_path(directory.parent / "checkpoints", experiment, seed, step)
            with source.open("rb") as stream:
                original = pickle.load(stream)
            eligible_profile(original["provenance"], profiles[seed])
            if original["seed"] != seed or original["next_step"] != step:
                raise ValueError("Transfer checkpoint boundary mismatch")
            adapted = copy.deepcopy(original)
            adapted["provenance"] = profiles[seed]
            target = checkpoint_path(checkpoints, experiment, seed, step)
            with target.open("xb") as stream:
                pickle.dump(adapted, stream, protocol=pickle.HIGHEST_PROTOCOL)
            receipt(source)
            receipt(target)
        source_config = experiment.get("seed_configs", {}).get(str(seed), experiment["config"])
        registry = json.loads((ROOT / source_config).read_text())
        plan = registry["states"][experiment["state"]]["plans"][experiment["starting_plan"]]
        plan["output_dir"] = result["input_dir"]
        plan["checkpoint_dir"] = str(checkpoints.relative_to(ROOT))
        config = destination / f"seed{seed}.json"
        with config.open("x") as stream:
            json.dump(registry, stream, indent=2)
            stream.write("\n")
        receipt(config)
        result["seed_configs"][str(seed)] = str(config.relative_to(ROOT))
        result["expected_checkpoint_provenance"][str(seed)] = profiles[seed]
        with originals[seed].open("rb") as stream:
            source_checkpoint = pickle.load(stream)
        records.append({"seed": seed, "source_provenance": source_checkpoint["provenance"],
                        "target_provenance": profiles[seed], "last_source_step": experiment["steps"] - 1,
                        "first_new_segment_step": experiment["steps"], "assignment_and_rng_preserved": True})
    result["config"] = result["seed_configs"][str(experiment["seeds"][0])]
    return result, {"files": files, "chains": records}


def validate_receipts(experiment):
    for item in experiment.get("platform_transitions", []):
        path = ROOT / item["path"]
        path.resolve().relative_to(ROOT)
        if file_sha256(path) != item["sha256"]:
            raise ValueError("Platform transition receipt changed")
        for name, expected in json.loads(path.read_text())["files"].items():
            source = ROOT / name
            source.resolve().relative_to(ROOT)
            if file_sha256(source) != expected:
                raise ValueError("Platform transition source or adapter changed")
