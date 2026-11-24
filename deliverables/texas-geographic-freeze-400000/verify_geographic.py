"""Reproduce the Texas geographic audit and review the frozen chain histories."""

import argparse
import hashlib
import json
import math
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
from PIL import Image, ImageChops

from paper.geographic_continue import GEOGRAPHIC, Geography
from paper.review_precision import half_comparison, independent_difference
from src.analysis.audit_rebuild_campaign import METRICS, load_chain


def read_json(path):
    return json.loads(path.read_text())


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def check_reproduction(original, reproduced):
    for field in ("geographic_diagnostics.json", "window_stability.csv"):
        if (original / field).read_bytes() != (reproduced / field).read_bytes():
            raise ValueError(f"Geographic reproduction differs: {field}")
    with Image.open(original / "geographic_traces.png") as saved, Image.open(
        reproduced / "geographic_traces.png"
    ) as generated:
        if saved.size != generated.size or ImageChops.difference(
            saved.convert("RGB"), generated.convert("RGB")
        ).getbbox():
            raise ValueError("Geographic trace pixels differ")


def starting_map_review(arrays, entries, metrics, warmup, mcse_field):
    baseline, dispersed = "tx_rebuild", "tx_dispersed"
    rows = {}
    for metric in metrics:
        def summary(cohort):
            sample = arrays[cohort][metric]
            selected = sample[:, warmup]
            value = entries[cohort][metric][mcse_field]
            mcse = value["value"] if isinstance(value, dict) else value
            return {
                "mean": float(selected.mean()),
                "mcse_mean": mcse,
                "half_history": half_comparison(selected),
            }

        left, right = summary(baseline), summary(dispersed)
        rows[metric] = {
            baseline: left,
            dispersed: right,
            **independent_difference(left["mean"], right["mean"], left["mcse_mean"], right["mcse_mean"]),
        }
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--paper-source", required=True, type=Path)
    parser.add_argument("--milestone", required=True, type=Path)
    parser.add_argument("--wave-manifest", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()

    root = Path.cwd()
    paper = args.paper_source.resolve()
    milestone = args.milestone.resolve()
    geography = milestone / "geography"
    snapshot = read_json(milestone / "primary/snapshot/manifest.json")["experiments"]
    wave = read_json(args.wave_manifest)["experiments"]
    primary = read_json(milestone / "primary/audit/diagnostics.json")
    geographic = read_json(geography / "geographic_diagnostics.json")
    scores = pd.read_csv(geography / "geographic_scores.csv", float_precision="round_trip")
    steps = 400_000
    if set(snapshot) != {"tx_rebuild", "tx_dispersed"} or any(
        (e["steps"], e["warmup"]) != (steps, 500) for e in snapshot.values()
    ):
        raise ValueError("Unexpected Texas freeze boundary")

    primary_arrays, geographic_arrays, terminal_rows = {}, {}, []
    for cohort, definition in snapshot.items():
        chains, geographies = [], []
        spec = SimpleNamespace(**{**definition, "input_dir": root / definition["input_dir"]})
        for seed in definition["seeds"]:
            trace = load_chain(spec, seed)
            measured = scores[(scores.group == cohort) & (scores.seed == seed)].sort_values("step")
            expected_steps = np.arange(99, steps, 100)
            if not np.array_equal(measured.step, expected_steps) or not np.array_equal(
                trace.iloc[expected_steps].plan_hash.to_numpy(), measured.plan_hash.to_numpy()
            ):
                raise ValueError(f"Geographic coverage or plan hash differs for seed {seed}")
            chains.append(trace)
            geographies.append(measured)
            terminal_rows.append(measured.index[-1])
        primary_arrays[cohort] = {
            metric: np.stack([chain[metric].to_numpy(float) for chain in chains]) for metric in METRICS
        }
        geographic_arrays[cohort] = {
            metric: np.stack([chain[metric].to_numpy(float) for chain in geographies])
            for metric in GEOGRAPHIC
        }
    if len(scores) != len(terminal_rows) * (steps // 100):
        raise ValueError("Unexpected geographic score rows")

    # Recalculate the terminal geographic measurements from each saved assignment.
    scorer = Geography(root, paper, paper / "outputs/analysis/geographic_measurement_20261109")
    scorer.table = scores.drop(index=terminal_rows)
    for cohort in snapshot:
        scorer.update(cohort, wave[cohort])
    row_keys = ["group", "seed", "step", "plan_hash"]
    actual = scorer.table[scorer.table.step == steps - 1].sort_values(row_keys)
    expected = scores.loc[terminal_rows].sort_values(row_keys)
    if not np.array_equal(actual[row_keys].to_numpy(), expected[row_keys].to_numpy()):
        raise ValueError("Terminal geographic checkpoint identities differ")
    np.testing.assert_allclose(actual[list(GEOGRAPHIC)], expected[list(GEOGRAPHIC)], rtol=1e-10, atol=1e-10)

    # Recreate every audit number and plot from the complete archived score series.
    scorer.table = scores
    scorer.update = lambda *_: None
    regenerated = scorer.audit("tx", snapshot, args.output_dir)
    if not regenerated["geographic_screens_pass"]:
        raise ValueError("Reproduced geographic convergence screens failed")
    check_reproduction(geography, args.output_dir)

    primary_entries = {key: value["diagnostics"] for key, value in primary["experiments"].items()}
    geographic_entries = {key: value["metrics"] for key, value in geographic["cohorts"].items()}
    primary_review = starting_map_review(
        primary_arrays, primary_entries, METRICS, slice(500, None), "mcse_mean"
    )
    geographic_review = starting_map_review(
        geographic_arrays, geographic_entries, GEOGRAPHIC, slice(5, None), "mcse_mean"
    )
    for review in (primary_review, geographic_review):
        for row in review.values():
            if not math.isfinite(row["combined_mcse"]) or any(
                row[cohort]["half_history"][field]["status"] != "finite"
                for cohort in snapshot for field in ("first_mcse_mean", "second_mcse_mean")
            ):
                raise ValueError("Nonfinite precision or half-history diagnostic")
    record = {
        "steps_per_chain": steps,
        "complete_geographic_score_rows": len(scores),
        "terminal_measurements_recomputed": len(terminal_rows) * len(GEOGRAPHIC),
        "geographic_audit_and_windows_byte_identical": True,
        "geographic_trace_pixels_identical": True,
        "warmup_state_count": 500,
        "geographic_checkpoint_spacing": 100,
        "starting_map_comparison": "Dispersed-minus-baseline means and combined Monte Carlo error are descriptive.",
        "primary": primary_review,
        "geographic": geographic_review,
        "checksums": {str(path.relative_to(root)): sha(path) for path in (
            geography / "geographic_scores.csv", geography / "geographic_diagnostics.json",
            milestone / "primary/audit/diagnostics.json", args.wave_manifest.resolve()
        )},
        "research_ready": False,
    }
    (args.output_dir / "precision_stability.json").write_text(
        json.dumps(record, indent=2, allow_nan=False) + "\n"
    )
    print(f"Verified {len(scores)} geographic score identities and {record['terminal_measurements_recomputed']} terminal measurements.")


if __name__ == "__main__":
    main()
