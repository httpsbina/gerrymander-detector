"""Audit new-source chains separately and jointly within each NC geography.

Numerical screening is not research readiness. No cross-geography pooling,
calibrated p-values, or silently omitted diagnostics are supported.
"""

import argparse
import json
from pathlib import Path
import pickle
import re
from types import SimpleNamespace
import sys
import warnings

import arviz as az
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.analysis.audit_ensemble_chains import load_chain
from src.chain.checkpoint_integrity import file_sha256

METRICS = ("dem_seats", "efficiency_gap", "cut_edges", "mean_median")


def campaign_segments(directory, experiment):
    seeds = experiment["seeds"]
    if len(seeds) < 2 or len(set(seeds)) != len(seeds):
        raise ValueError("Campaign requires at least two distinct configured seeds")
    tag = f"{experiment['epsilon']:g}".replace(".", "p")
    pattern = re.escape(experiment["prefix"] + "_chain_eps" + tag) + r"_seed(-?\d+)_steps\d+-\d+\.csv"
    files = sorted(directory.glob("*.csv"))
    for path in files:
        match = re.fullmatch(pattern, path.name)
        if match is None or int(match.group(1)) not in seeds:
            raise ValueError(f"Unconfigured chain segment must be reviewed, not omitted: {path.name}")
    return files


def check_final_checkpoint(checkpoint, experiment, seed, chain, source_code):
    """Check trusted, locally produced campaign checkpoints against their records."""
    if checkpoint.get("version") != 2:
        raise ValueError("Unverifiable checkpoint version")
    for name, expected in (("seed", seed), ("next_step", experiment["steps"]),
                           ("epsilon", experiment["epsilon"]),
                           ("node_repeats", experiment["node_repeats"]),
                           ("plan_hash", chain.plan_hash.iloc[-1]), ("pythonhashseed", "0")):
        if checkpoint.get(name) != expected:
            raise ValueError(f"Final checkpoint mismatch: {name}")
    provenance = checkpoint["provenance"]
    for name, expected in (
        ("dataset_sha256", experiment["dataset_sha256"]),
        ("runner_sha256", source_code["src/chain/run_ensemble.py"]),
        ("checkpoint_code_sha256", source_code["src/chain/checkpoint_integrity.py"]),
    ):
        if provenance.get(name) != expected:
            raise ValueError(f"Final checkpoint provenance mismatch: {name}")
    configuration = provenance["configuration"]
    for name, expected in (("state", experiment["prefix"]), ("sample_every", 1),
                           ("epsilon", experiment["epsilon"]),
                           ("node_repeats", experiment["node_repeats"])):
        if configuration.get(name) != expected:
            raise ValueError(f"Checkpoint configuration mismatch: {name}")
    return provenance


def diagnostics(samples):
    outputs, issues, warning_messages = {}, [], []
    minimum_ess = max(400, 100 * samples.shape[0])
    calls = {
        "rank_split_rhat": lambda: az.rhat(samples, method="rank"),
        "bulk_ess": lambda: az.ess(samples, method="bulk"),
        "tail_ess": lambda: az.ess(samples, method="tail", prob=(0.05, 0.95)),
        "mcse_mean": lambda: az.mcse(samples, method="mean"),
        "mcse_sd": lambda: az.mcse(samples, method="sd"),
        "mcse_q05": lambda: az.mcse(samples, method="quantile", prob=0.05),
        "mcse_q95": lambda: az.mcse(samples, method="quantile", prob=0.95),
    }
    for name, call in calls.items():
        try:
            with warnings.catch_warnings(record=True) as captured:
                warnings.simplefilter("always")
                value = float(np.asarray(call()).item())
            warning_messages.extend(str(item.message) for item in captured)
            if not np.isfinite(value):
                outputs[name] = None
                issues.append(f"{name}: nonfinite")
            else:
                outputs[name] = value
        except Exception as exc:
            outputs[name] = None
            issues.append(f"{name}: {type(exc).__name__}: {exc}")
    outputs["all_finite"] = not issues
    outputs["issues"] = issues
    outputs["warnings"] = warning_messages
    outputs["screening_flags"] = []
    for name, condition, message in (
        ("rank_split_rhat", lambda value: value >= 1.01, "rank R-hat at or above 1.01"),
        ("bulk_ess", lambda value: value < minimum_ess, f"bulk ESS below {minimum_ess}"),
        ("tail_ess", lambda value: value < minimum_ess, f"tail ESS below {minimum_ess}"),
    ):
        if outputs[name] is not None and condition(outputs[name]):
            outputs["screening_flags"].append(message)
    outputs["ess_screening_minimum"] = minimum_ess
    return outputs


def summarize_chains(chains, experiment, warmup):
    rows = []
    for seed, chain in chains.items():
        retained = chain.iloc[warmup:]
        row = {"experiment": experiment, "seed": seed, "states": len(chain),
               "warmup": warmup, "retained_states": len(retained),
               "unique_plans": int(chain.plan_hash.nunique()),
               "plan_change_rate": float((chain.plan_hash.to_numpy()[1:] != chain.plan_hash.to_numpy()[:-1]).mean())}
        for metric in METRICS:
            row[metric + "_mean"] = float(retained[metric].mean())
            row[metric + "_min"] = float(retained[metric].min())
            row[metric + "_max"] = float(retained[metric].max())
            values = retained[metric].to_numpy(float)
            row[metric + "_first_last_window_mean_difference"] = float(values[-1000:].mean() - values[:1000].mean())
            for lag in (1, 10, 50, 100):
                if len(values) > lag and np.std(values[:-lag]) > 0 and np.std(values[lag:]) > 0:
                    row[f"{metric}_autocorrelation_lag{lag}"] = float(np.corrcoef(values[:-lag], values[lag:])[0, 1])
                else:
                    row[f"{metric}_autocorrelation_lag{lag}"] = None
        rows.append(row)
    return rows


def audit(manifest_path, destination, selected=None):
    manifest = json.loads(manifest_path.read_text())
    for name in ("src/chain/run_ensemble.py", "src/chain/checkpoint_integrity.py"):
        if file_sha256(ROOT / name) != manifest["source_code"][name]:
            raise ValueError(f"Sampler source differs from recorded campaign: {name}")
    report = {"research_ready": False, "manifest_sha256": file_sha256(manifest_path),
              "experiments": {}, "joint_nc": {}, "metric_definitions": {
                  "mean_median": "GerryChain Democratic median-minus-mean two-party district share",
                  "efficiency_gap": "GerryChain two-party efficiency gap; descriptive modeled votes"},
              "screening": {"rhat_strict_upper": 1.01, "ess_floor": "max(400, 100 * chains)",
                            "meaning": "Conservative numerical flags, not a complete project acceptance criterion"},
              "unresolved": ["Election source/canvass and NC privacy-noise uncertainties",
                             "MCSE and stability acceptance criteria require scientific review",
                             "No historical-chain continuation or source equivalence is established",
                             "ReCom is not established as uniform or fully legally constrained"]}
    summaries, windows, diagnostic_rows = [], [], []
    loaded = {}
    definitions = manifest["experiments"]
    if selected is not None and set(selected) - set(definitions):
        raise ValueError("Unknown selected experiment")
    for key, experiment in definitions.items():
        if selected is not None and key not in selected:
            continue
        entry = {"integrity": "unavailable", "diagnostics": {}, "warmup_sensitivity": {}, "files": []}
        report["experiments"][key] = entry
        try:
            dataset = (ROOT / experiment["dataset"]).resolve()
            dataset.relative_to(ROOT)
            if file_sha256(dataset) != experiment["dataset_sha256"]:
                raise ValueError("Dataset hash differs from the campaign manifest")
            directory = (ROOT / experiment["input_dir"]).resolve()
            directory.relative_to(ROOT)
            args = SimpleNamespace(input_dir=directory, prefix=experiment["prefix"],
                                   epsilon=experiment["epsilon"], steps=experiment["steps"],
                                   districts=experiment["districts"])
            files = campaign_segments(directory, experiment)
            chains = {seed: load_chain(args, seed) for seed in experiment["seeds"]}
            if len({chain.plan_hash.iloc[0] for chain in chains.values()}) != 1:
                raise ValueError("Different initial maps within one starting-map group")
            for chain in chains.values():
                if any(metric not in chain for metric in METRICS):
                    raise ValueError("Required diagnostic metric missing")
                if not np.isfinite(chain[list(METRICS)].to_numpy(float)).all():
                    raise ValueError("Nonfinite trace data")
            checkpoint_records, provenances = [], []
            for seed, chain in chains.items():
                tag = f"{experiment['epsilon']:g}".replace(".", "p")
                path = directory.parent / "checkpoints" / (
                    f"{experiment['prefix']}_checkpoint_eps{tag}_seed{seed}_next{experiment['steps']}.pkl")
                # Only load this campaign's trusted local pickle, never an arbitrary external checkpoint.
                with path.open("rb") as stream:
                    checkpoint = pickle.load(stream)
                provenances.append(check_final_checkpoint(checkpoint, experiment, seed, chain, manifest["source_code"]))
                checkpoint_records.append({"path": str(path), "sha256": file_sha256(path)})
            if any(value != provenances[0] for value in provenances[1:]):
                raise ValueError("Checkpoint provenance differs within a starting-map group")
            entry["checkpoints"] = checkpoint_records
            entry["checkpoint_provenance"] = provenances[0]
            entry["integrity"] = "pass"
            for path in files:
                entry["files"].append({"path": str(path), "sha256": file_sha256(path)})
            warmup, window = experiment["warmup"], experiment["window"]
            summaries.extend(summarize_chains(chains, key, warmup))
            for seed, chain in chains.items():
                for start in range(warmup, len(chain), window):
                    part = chain.iloc[start:start + window]
                    windows.append({"experiment": key, "seed": seed, "first_step": int(part.step.iloc[0]),
                                    "last_step": int(part.step.iloc[-1]), "states": len(part),
                                    **{metric + "_mean": float(part[metric].mean()) for metric in METRICS}})
            for burn in sorted({0, 250, warmup, 1000}):
                if burn >= experiment["steps"] - 3:
                    entry["warmup_sensitivity"][str(burn)] = {"status": "unavailable; insufficient retained states"}
                    continue
                by_metric = {}
                for metric in METRICS:
                    samples = np.stack([chain.iloc[burn:][metric].to_numpy(float) for chain in chains.values()])
                    result = diagnostics(samples)
                    by_metric[metric] = result
                    diagnostic_rows.append({"experiment": key, "warmup": burn, "metric": metric,
                                            "ess_screening_minimum": result["ess_screening_minimum"],
                                            **{name: result[name] for name in (
                                                "rank_split_rhat", "bulk_ess", "tail_ess", "mcse_mean", "mcse_sd", "mcse_q05", "mcse_q95")}})
                entry["warmup_sensitivity"][str(burn)] = by_metric
                if burn == warmup:
                    entry["diagnostics"] = by_metric
            loaded[key] = chains
        except Exception as exc:
            entry["integrity"] = "fail"
            entry["error"] = f"{type(exc).__name__}: {exc}"
    for geometry in ("nc_block_union", "nc_precinct_sensitivity", "nc_population_sensitivity"):
        keys = [geometry + "_2023", geometry + "_2025"]
        if not all(key in loaded for key in keys):
            report["joint_nc"][geometry] = {"status": "unavailable; both complete starting-map groups required"}
            continue
        left, right = (definitions[key] for key in keys)
        for name in ("dataset_sha256", "epsilon", "node_repeats", "steps", "warmup"):
            if left[name] != right[name]:
                raise ValueError("Cannot pool incompatible NC starting-map groups")
        if set(left["seeds"]) & set(right["seeds"]):
            raise ValueError("NC joint analysis requires distinct seeds across initialization groups")
        joint = {"status": "computed", "diagnostics": {}, "warmup_sensitivity": {},
                 "starting_map_mean_difference_2025_minus_2023": {}}
        for burn in sorted({0, 250, left["warmup"], 1000}):
            joint["warmup_sensitivity"][str(burn)] = {}
            for metric in METRICS:
                samples = np.stack([chain.iloc[burn:][metric].to_numpy(float)
                                    for key in keys for chain in loaded[key].values()])
                result = diagnostics(samples)
                joint["warmup_sensitivity"][str(burn)][metric] = result
                diagnostic_rows.append({"experiment": geometry + "_joint", "warmup": burn,
                                        "metric": metric, "ess_screening_minimum": result["ess_screening_minimum"],
                                        **{name: result[name] for name in (
                                            "rank_split_rhat", "bulk_ess", "tail_ess", "mcse_mean", "mcse_sd", "mcse_q05", "mcse_q95")}})
        for metric in METRICS:
            joint["diagnostics"][metric] = joint["warmup_sensitivity"][str(left["warmup"])][metric]
            means = [np.mean([chain.iloc[left["warmup"]:][metric].mean()
                              for chain in loaded[key].values()]) for key in keys]
            joint["starting_map_mean_difference_2025_minus_2023"][metric] = float(means[1] - means[0])
        report["joint_nc"][geometry] = joint
    report["condition_mean_differences"] = {}
    comparisons = [
        ("tx_population", "tx_rebuild", "tx_population_sensitivity"),
        *[(f"nc_graph_{year}", f"nc_block_union_{year}", f"nc_precinct_sensitivity_{year}")
          for year in (2023, 2025)],
        *[(f"nc_population_{year}", f"nc_block_union_{year}", f"nc_population_sensitivity_{year}")
          for year in (2023, 2025)],
    ]
    for name, baseline, sensitivity in comparisons:
        entry = {"baseline": baseline, "sensitivity": sensitivity,
                 "interpretation": "Descriptive sensitivity-minus-baseline means; conditions are not pooled and paired seed labels do not establish independent uncertainty"}
        if baseline in loaded and sensitivity in loaded:
            entry["metrics"] = {}
            for metric in METRICS:
                means = [np.mean([chain.iloc[definitions[key]["warmup"]:][metric].mean()
                                  for chain in loaded[key].values()]) for key in (baseline, sensitivity)]
                entry["metrics"][metric] = float(means[1] - means[0])
        else:
            entry["status"] = "unavailable; both complete conditions required"
        report["condition_mean_differences"][name] = entry
    destination.mkdir(parents=True, exist_ok=False)
    with (destination / "diagnostics.json").open("x") as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write("\n")
    pd.DataFrame(summaries).to_csv(destination / "chain_summary.csv", index=False, mode="x")
    pd.DataFrame(windows).to_csv(destination / "windows.csv", index=False, mode="x")
    pd.DataFrame(diagnostic_rows).to_csv(destination / "diagnostics.csv", index=False, mode="x")
    print(json.dumps({key: {"integrity": entry["integrity"], "primary": entry["diagnostics"]}
                      for key, entry in report["experiments"].items()}, indent=2))
    print("RESEARCH-READY: NO")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--experiments", nargs="+")
    args = parser.parse_args()
    for path in (args.manifest, args.output_dir):
        path.resolve().relative_to(ROOT)
    if args.output_dir.exists():
        raise FileExistsError("Refusing existing diagnostic output directory")
    audit(args.manifest, args.output_dir, args.experiments)


if __name__ == "__main__":
    main()
