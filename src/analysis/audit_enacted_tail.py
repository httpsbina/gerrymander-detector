"""Describe enacted-seat tail indicators without calibrated probability claims."""

import argparse
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.analysis.audit_ensemble_chains import load_chain
from src.analysis.audit_rebuild_campaign import diagnostics
from src.chain.checkpoint_integrity import file_sha256


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--audit-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    for path in (args.manifest, args.audit_root, args.output_dir):
        path.resolve().relative_to(ROOT)
    if args.output_dir.exists():
        raise FileExistsError("Refusing existing enacted-tail audit directory")
    manifest = json.loads(args.manifest.read_text())
    sources = {}
    for state, short in (("texas", "tx"), ("north_carolina", "nc")):
        path = args.audit_root / f"{short}_block_audit/source_audit.json"
        source = json.loads(path.read_text())
        if source["tabular_integrity"] != "pass":
            raise ValueError("Block benchmark did not pass tabular integrity")
        sources[state] = {"path": str(path), "sha256": file_sha256(path),
                          "threshold": source["plans"]["2025"]["dem_modeled_seats"]}
    rows, groups, results = [], {}, {}
    for key, experiment in manifest["experiments"].items():
        directory = (ROOT / experiment["input_dir"]).resolve()
        directory.relative_to(ROOT)
        spec = SimpleNamespace(input_dir=directory, prefix=experiment["prefix"],
                               epsilon=experiment["epsilon"], steps=experiment["steps"],
                               districts=experiment["districts"])
        threshold = sources[experiment["state"]]["threshold"]
        chains = {seed: load_chain(spec, seed) for seed in experiment["seeds"]}
        groups[key] = (experiment, threshold, chains)
        for seed, chain in chains.items():
            retained = chain.iloc[experiment["warmup"]:]
            observed = retained[retained.dem_seats <= threshold]
            rows.append({"experiment": key, "seed": seed, "threshold": threshold,
                         "retained_states": len(retained), "observed_states": len(observed),
                         "distinct_observed_plan_hashes": observed.plan_hash.nunique(),
                         "descriptive_fraction": len(observed) / len(retained),
                         "first_observed_step": int(observed.step.min()) if len(observed) else None,
                         "last_observed_step": int(observed.step.max()) if len(observed) else None})
    for geometry in ("nc_block_union", "nc_precinct_sensitivity", "nc_population_sensitivity"):
        left, right = [groups[geometry + suffix] for suffix in ("_2023", "_2025")]
        if left[1] != right[1] or any(left[0][name] != right[0][name] for name in (
            "dataset_sha256", "epsilon", "node_repeats", "steps", "warmup")) or set(left[2]) & set(right[2]):
            raise ValueError("Incompatible NC groups")
        groups[geometry + "_joint"] = (left[0], left[1], {**left[2], **right[2]})
    for key, (experiment, threshold, chains) in groups.items():
        results[key] = {"threshold": threshold, "warmup_sensitivity": {}}
        for warmup in sorted({0, 250, experiment["warmup"], 1000}):
            indicators = np.stack([(chain.iloc[warmup:].dem_seats <= threshold).to_numpy(float)
                                   for chain in chains.values()])
            results[key]["warmup_sensitivity"][str(warmup)] = diagnostics(indicators)
    args.output_dir.mkdir(parents=True, exist_ok=False)
    pd.DataFrame(rows).to_csv(args.output_dir / "enacted_tail_counts.csv", index=False, mode="x")
    report = {"research_ready": False, "manifest_sha256": file_sha256(args.manifest),
              "block_benchmarks": sources, "groups": results,
              "interpretation": "Descriptive frequencies and dependence diagnostics for modeled seat counts at or below the block-scored enacted threshold; not calibrated p-values or established target probabilities. Zero observed outcomes do not imply zero probability."}
    with (args.output_dir / "enacted_tail_diagnostics.json").open("x") as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(pd.DataFrame(rows).to_string(index=False))
    print("RESEARCH-READY: NO")


if __name__ == "__main__":
    main()
