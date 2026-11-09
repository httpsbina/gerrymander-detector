"""Review frozen Monte Carlo precision without assigning new acceptance rules."""

import argparse
import csv
import hashlib
from importlib import metadata
import json
import math
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import warnings

import arviz as az
import numpy as np

from src.analysis.audit_ensemble_chains import load_chain

ROOT = Path(__file__).resolve().parents[1]
METRICS = {"dem_seats": ("Democratic seats", "seats", 1),
           "efficiency_gap": ("Efficiency gap", "percentage points", 100),
           "cut_edges": ("Cut edges", "edges", 1),
           "mean_median": ("Median minus mean", "percentage points", 100)}
SOURCES = ["https://arxiv.org/html/1903.08008v5",
           "https://mc-stan.org/posterior/reference/mcse_mean.html",
           "https://mc-stan.org/posterior/reference/mcse_quantile.html"]


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def finite_call(call):
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            value = float(np.asarray(call()).item())
            result = {"value": value if math.isfinite(value) else None,
                      "status": "finite" if math.isfinite(value) else "nonfinite"}
        except Exception as exc:
            result = {"value": None, "status": "failed", "error": f"{type(exc).__name__}: {exc}"}
    result["warnings"] = [str(item.message) for item in caught]
    return result


def half_comparison(samples):
    samples = np.asarray(samples, dtype=float)
    if samples.ndim != 2 or not np.isfinite(samples).all() or samples.shape[1] < 8:
        raise ValueError("Finite complete chain arrays required")
    split = samples.shape[1] // 2
    first, second = samples[:, :split], samples[:, split:]
    return {"first_states_per_chain": first.shape[1], "second_states_per_chain": second.shape[1],
            "first_mean": float(first.mean()), "second_mean": float(second.mean()),
            "second_minus_first": float(second.mean() - first.mean()),
            "first_mcse_mean": finite_call(lambda: az.mcse(first, method="mean")),
            "second_mcse_mean": finite_call(lambda: az.mcse(second, method="mean"))}


def independent_difference(first_mean, second_mean, first_mcse, second_mcse):
    error = math.hypot(first_mcse, second_mcse)
    return {"second_minus_first": second_mean - first_mean,
            "combined_mcse": error,
            "difference_over_combined_mcse": (second_mean - first_mean) / error if error > 0 else None}


def tail_diagnostics(samples, threshold):
    indicator = np.asarray(samples) <= threshold
    counts = indicator.sum(axis=1).astype(int).tolist()
    constant = bool(np.all(indicator == indicator.flat[0]))
    unavailable = {"value": None, "status": "unavailable_constant_indicator", "warnings": []}
    return {"threshold": threshold, "events_by_chain": counts,
            "event_runs_by_chain": [int(row[0]) + int(np.sum(row[1:] & ~row[:-1])) for row in indicator],
            "retained_by_chain": [indicator.shape[1]] * indicator.shape[0],
            "events": sum(counts), "observations": indicator.size, "frequency": float(indicator.mean()),
            "constant_chain_indices": [i for i, row in enumerate(indicator) if np.all(row == row[0])],
            "mcse_frequency": dict(unavailable) if constant else finite_call(lambda: az.mcse(indicator, method="mean")),
            "ess_mean_indicator": dict(unavailable) if constant else finite_call(lambda: az.ess(indicator, method="mean")),
            "rank_split_rhat_indicator": dict(unavailable) if constant else finite_call(lambda: az.rhat(indicator, method="rank"))}


def check_freeze(root, name, fingerprints):
    path = root / name
    frozen = json.loads(path.read_text())
    if frozen["status"] != "primary_convergence_frozen":
        raise ValueError("Registered primary freeze required")
    fingerprints[name] = sha(path)
    for filename, expected in frozen["checksums"].items():
        source = (root / filename).resolve(); source.relative_to(root)
        actual = sha(source)
        if actual != expected:
            raise ValueError(f"Frozen input checksum mismatch: {filename}")
        fingerprints[filename] = actual
    return frozen


def collect(root):
    registry_path = root / "configs/paper_freezes.json"
    registry = json.loads(registry_path.read_text())
    fingerprints = {str(registry_path.relative_to(root)): sha(registry_path)}
    review = {}
    for state, name in registry.items():
        frozen = check_freeze(root, name, fingerprints)
        manifest = json.loads((root / frozen["manifest"]).read_text())
        audit = json.loads((root / frozen["audit_dir"] / "diagnostics.json").read_text())
        if audit["manifest_sha256"] != sha(root / frozen["manifest"]):
            raise ValueError("Frozen manifest/audit mismatch")
        with (root / frozen["audit_dir"] / "chain_summary.csv").open() as stream:
            recorded = {(row["experiment"], int(row["seed"])): row for row in csv.DictReader(stream)}
        with (root / frozen["audit_dir"] / "windows.csv").open() as stream:
            windows = list(csv.DictReader(stream))
        arrays, seeds, specifications = {}, {}, {}
        chain_rows, initial_seats = [], []
        for group, spec in manifest["experiments"].items():
            args = SimpleNamespace(**{**spec, "input_dir": root / spec["input_dir"]})
            frames = [load_chain(args, seed) for seed in spec["seeds"]]
            arrays[group] = {metric: np.stack([frame[metric].to_numpy(float) for frame in frames])
                             for metric in METRICS}
            seeds[group] = spec["seeds"]; specifications[group] = spec
            for seed, frame in zip(spec["seeds"], frames):
                initial_seats.append(int(frame.dem_seats.iloc[0]))
                retained = frame.iloc[spec["warmup"]:]
                if not np.isfinite(retained[list(METRICS)].to_numpy()).all():
                    raise ValueError("Nonfinite frozen observations")
                for metric in METRICS:
                    observed = recorded[(group, seed)]
                    mean = float(retained[metric].mean())
                    delta = float(retained[metric].iloc[-1000:].mean() - retained[metric].iloc[:1000].mean())
                    if not math.isclose(mean, float(observed[metric + "_mean"]), abs_tol=1e-12, rel_tol=1e-12):
                        raise ValueError("Frozen chain mean mismatch")
                    if not math.isclose(delta, float(observed[metric + "_first_last_window_mean_difference"]), abs_tol=1e-12, rel_tol=1e-12):
                        raise ValueError("Frozen window comparison mismatch")
                    samples = retained[metric].to_numpy(float); midpoint = len(samples) // 2
                    chain_rows.append({"group": group, "seed": seed, "metric": metric, "mean": mean,
                        "first_last_1000_difference": delta, "first_half_mean": float(samples[:midpoint].mean()),
                        "second_half_mean": float(samples[midpoint:].mean()),
                        "half_difference": float(samples[midpoint:].mean() - samples[:midpoint].mean())})
        cohort_names = list(arrays)
        if len(cohort_names) != 2:
            raise ValueError("Two complete starting cohorts required")
        specs = list(specifications.values()); warmup = specs[0]["warmup"]
        if any((spec["steps"], spec["warmup"]) != (specs[0]["steps"], warmup) for spec in specs):
            raise ValueError("Unequal complete cohort histories")
        entries = {key: audit["experiments"][key] for key in cohort_names}
        entries["joint"] = audit["joint_texas"] if state == "texas" else audit["joint_nc"]["nc_block_union"]
        arrays["joint"] = {metric: np.concatenate([arrays[group][metric] for group in cohort_names]) for metric in METRICS}
        seeds["joint"] = [seed for group in cohort_names for seed in seeds[group]]
        summary, halves, warmups = [], [], []
        for group, by_metric in arrays.items():
            for metric, complete in by_metric.items():
                samples = complete[:, warmup:]; stored = entries[group]["diagnostics"][metric]
                calculated = finite_call(lambda: az.mcse(samples, method="mean"))
                if calculated["status"] != "finite" or not math.isclose(calculated["value"], stored["mcse_mean"], abs_tol=1e-12, rel_tol=1e-12):
                    raise ValueError("Frozen mean MCSE failed reproduction")
                summary.append({"group": group, "metric": metric, "chains": len(samples),
                    "retained_per_chain": samples.shape[1], "mean": float(samples.mean()),
                    "sample_sd": float(samples.std(ddof=1)), "two_mcse_scale": 2 * stored["mcse_mean"],
                    **{field: stored[field] for field in ["mcse_mean", "mcse_sd", "mcse_q05", "mcse_q95", "rank_split_rhat", "bulk_ess", "tail_ess"]},
                    "mcse_over_sample_sd": stored["mcse_mean"] / float(samples.std(ddof=1))})
                halves.append({"group": group, "metric": metric, **half_comparison(samples)})
                reference = float(samples.mean())
                for burn, diagnostics in entries[group]["warmup_sensitivity"].items():
                    retained = complete[:, int(burn):]
                    warmups.append({"group": group, "metric": metric, "warmup": int(burn),
                                    "mean": float(retained.mean()), "difference_from_registered_warmup": float(retained.mean()) - reference,
                                    "mcse_mean": diagnostics[metric]["mcse_mean"],
                                    "q05": float(np.quantile(retained, .05)), "q95": float(np.quantile(retained, .95))})
        differences = []
        for metric in METRICS:
            rows = [next(row for row in summary if row["group"] == group and row["metric"] == metric) for group in cohort_names]
            differences.append({"metric": metric, "first_group": cohort_names[0], "second_group": cohort_names[1],
                                **independent_difference(rows[0]["mean"], rows[1]["mean"], rows[0]["mcse_mean"], rows[1]["mcse_mean"])})
        if state == "texas":
            paper = json.loads((ROOT / "paper/results.json").read_text())
            threshold = paper["_paper"]["texas"]["paper_outputs"]["enacted_democratic_seats"]
        else:
            initial = set(initial_seats)
            if len(initial) != 1: raise ValueError("NC enacted seat thresholds differ; separate comparisons required")
            threshold = initial.pop()
        tails = {group: {"seeds": seeds[group], **tail_diagnostics(by_metric["dem_seats"][:, warmup:], threshold)}
                 for group, by_metric in arrays.items()}
        review[state] = {"freeze_manifest": name, "steps_per_chain": specs[0]["steps"], "warmup": warmup,
            "cohorts": cohort_names, "summary": summary, "halves": halves, "warmups": warmups,
            "independent_cohort_differences": differences, "chains": chain_rows, "tail_indicator": tails,
            "recorded_windows": windows, "frozen_checksums_verified": len(frozen["checksums"])}
        print(state, "review computed", flush=True)
    packages = {}
    for line in (root / "requirements-research-macos-arm64-py312.txt").read_text().splitlines():
        if "==" in line:
            name, expected = line.split("==", 1); packages[name] = metadata.version(name)
            if packages[name] != expected: raise ValueError(f"Pinned package differs: {name}")
    return {"acceptance_status": "pending_scientific_review", "research_ready": False,
            "thresholds_changed": False, "process_nice": os.getpriority(os.PRIO_PROCESS, 0),
            "software": packages,
            "review_definition_checksums": {"paper/results.json": sha(ROOT / "paper/results.json")},
            "source_checksums": fingerprints, "code_sha256": sha(__file__), "references": SOURCES, "states": review}


def write_csv(path, rows):
    with path.open("x", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader(); writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(); root = args.source_root.resolve(); destination = args.output_dir.resolve()
    destination.relative_to(ROOT)
    if destination.exists(): raise FileExistsError(destination)
    report = collect(root)
    destination.mkdir(parents=True)
    (destination / "results.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    for name in ["summary", "chains", "warmups", "independent_cohort_differences"]:
        write_csv(destination / (name + ".csv"), [{"state": state, **row} for state,data in report["states"].items() for row in data[name]])
    half_rows = []
    for state, data in report["states"].items():
        for row in data["halves"]:
            half_rows.append({"state": state, **{key: value for key,value in row.items() if key not in ["first_mcse_mean", "second_mcse_mean"]},
                              "first_mcse_mean": row["first_mcse_mean"]["value"], "first_mcse_status": row["first_mcse_mean"]["status"],
                              "second_mcse_mean": row["second_mcse_mean"]["value"], "second_mcse_status": row["second_mcse_mean"]["status"]})
    write_csv(destination / "halves.csv", half_rows)
    print(destination)


if __name__ == "__main__":
    main()
