"""Verify that Texas initialization cohorts use identical sampling inputs."""

import json
from pathlib import Path
import warnings

import geopandas as gpd
from gerrychain import Graph

from src.chain.checkpoint_integrity import file_sha256
from src.data_prep.prepare_dispersed_texas_starts import kernel_signature

ROOT = Path(__file__).resolve().parents[2]


def verify_kernel_equivalence(baseline, dispersed):
    proof_path = (ROOT / dispersed["kernel_equivalence_file"]).resolve()
    proof_path.relative_to(ROOT)
    if file_sha256(proof_path) != dispersed["kernel_equivalence_sha256"]:
        raise ValueError("Kernel equivalence receipt changed")
    proof = json.loads(proof_path.read_text())
    frames = []
    for experiment, field in ((baseline, "original_dataset_sha256"),
                              (dispersed, "dispersed_dataset_sha256")):
        path = (ROOT / experiment["dataset"]).resolve()
        path.relative_to(ROOT)
        if file_sha256(path) != experiment["dataset_sha256"] or proof[field] != experiment["dataset_sha256"]:
            raise ValueError("Texas cohort dataset fingerprint mismatch")
        frame = gpd.read_file(path, layer="precincts")
        with warnings.catch_warnings(record=True):
            graph = Graph.from_geodataframe(frame, adjacency="rook")
        if kernel_signature(frame, graph) != proof["kernel_signature_sha256"]:
            raise ValueError("Texas graph, population or votes differ across cohorts")
        frames.append(frame)
    columns = ["UNIQUE_ID", "TOTPOP", "G24PREDHAR", "G24PRERTRU", "CONG_DIST"]
    if frames[0][columns].to_dict("list") != frames[1][columns].to_dict("list"):
        raise ValueError("Texas original unit ordering or attributes changed")
    if frames[0].geometry.to_wkb().tolist() != frames[1].geometry.to_wkb().tolist():
        raise ValueError("Texas geometry differs across cohorts")
    return proof
