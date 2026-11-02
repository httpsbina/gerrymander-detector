"""Compare saved partitions with unit- and population-weighted information distance."""

import argparse
import json
from pathlib import Path
import pickle
import sys

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.chain.checkpoint_integrity import file_sha256


def entropy(counts):
    values = np.asarray(counts, dtype=float)
    if not np.isfinite(values).all() or (values < 0).any() or values.sum() <= 0:
        raise ValueError("Information distance requires finite nonnegative mass with positive total")
    probabilities = values[values > 0] / values.sum()
    return float(-np.dot(probabilities, np.log2(probabilities)))


def information_distance(contingency):
    """VI = H(A|B) + H(B|A), in bits, on the supplied unit measure."""
    matrix = np.asarray(contingency, dtype=float)
    if matrix.ndim != 2:
        raise ValueError("A two-dimensional contingency table is required")
    value = 2 * entropy(matrix.ravel()) - entropy(matrix.sum(axis=1)) - entropy(matrix.sum(axis=0))
    if value < -1e-12:
        raise ValueError("Negative variation of information exceeds floating-point roundoff")
    return max(0.0, value)


def partition_distances(left, right, population):
    left = np.asarray(left)
    right = np.asarray(right)
    population = np.asarray(population, dtype=float)
    if left.ndim != 1 or left.shape != right.shape or left.shape != population.shape:
        raise ValueError("Assignments and population must have equal one-dimensional coverage")
    if pd.isna(left).any() or pd.isna(right).any():
        raise ValueError("Missing district assignment")
    if not np.isfinite(population).all() or (population < 0).any() or population.sum() <= 0:
        raise ValueError("Invalid population weights")
    _, a = np.unique(left, return_inverse=True)
    _, b = np.unique(right, return_inverse=True)
    nleft, nright = int(a.max()) + 1, int(b.max()) + 1
    return coded_distances(a, b, nleft, nright, population)


def coded_distances(a, b, nleft, nright, population):
    indices = a * nright + b
    units = np.bincount(indices, minlength=nleft * nright).reshape(nleft, nright)
    weighted = np.bincount(indices, weights=population, minlength=nleft * nright).reshape(nleft, nright)
    return information_distance(units), information_distance(weighted)


def lag_group(lag):
    if lag == 0:
        return "0"
    if lag < 500:
        return "1-499"
    if lag < 1000:
        return "500-999"
    if lag < 2000:
        return "1000-1999"
    return "2000+"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--checkpoint-audit", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    for path in (args.manifest, args.checkpoint_audit, args.output_dir):
        path.resolve().relative_to(ROOT)
    if args.output_dir.exists():
        raise FileExistsError("Refusing existing partition-distance output directory")
    manifest = json.loads(args.manifest.read_text())
    audit = json.loads(args.checkpoint_audit.read_text())
    if audit["manifest_sha256"] != file_sha256(args.manifest):
        raise ValueError("Checkpoint audit and campaign manifest differ")
    receipts = {}
    for item in audit["checkpoints"]:
        path = Path(item["path"]).resolve()
        path.relative_to(ROOT)
        receipts[path] = item["sha256"]
    conditions = {}
    for key, experiment in manifest["experiments"].items():
        condition = key.rsplit("_", 1)[0] if experiment["state"] == "north_carolina" else key
        conditions.setdefault(condition, []).append((key, experiment))
    args.output_dir.mkdir(parents=True, exist_ok=False)
    summaries, snapshot_rows, references = [], [], []
    pair_count, checkpoint_count = 0, 0
    for condition, definitions in conditions.items():
        first = definitions[0][1]
        for _, other in definitions[1:]:
            if any(first[name] != other[name] for name in (
                "dataset_sha256", "epsilon", "node_repeats", "steps", "warmup", "districts")):
                raise ValueError("Incompatible conditions cannot be compared")
        dataset = (ROOT / first["dataset"]).resolve()
        dataset.relative_to(ROOT)
        if file_sha256(dataset) != first["dataset_sha256"]:
            raise ValueError("Dataset differs from manifest")
        frame = gpd.read_file(dataset, layer="precincts", columns=["TOTPOP", "CONG_DIST"], ignore_geometry=True)
        population = frame.TOTPOP.to_numpy(float)
        reference = frame.CONG_DIST.astype(str).to_numpy()
        plans, seeds = [], set()
        for key, experiment in definitions:
            directory = (ROOT / experiment["input_dir"]).resolve().parent / "checkpoints"
            directory.relative_to(ROOT)
            tag = f"{experiment['epsilon']:g}".replace(".", "p")
            for seed in experiment["seeds"]:
                if seed in seeds:
                    raise ValueError("Duplicate seed within condition")
                seeds.add(seed)
                expected = sorted(set(range(100, experiment["steps"] + 1, 100)) | {experiment["steps"]})
                prefix = f"{experiment['prefix']}_checkpoint_eps{tag}_seed{seed}_next"
                files = sorted(directory.glob(prefix + "*.pkl"), key=lambda p: int(p.stem.split("_next")[-1]))
                if [int(p.stem.split("_next")[-1]) for p in files] != expected:
                    raise ValueError("Missing or unexpected checkpoint snapshot")
                for path, next_step in zip(files, expected):
                    if receipts.get(path) != file_sha256(path):
                        raise ValueError("Checkpoint fingerprint differs from prior complete audit")
                    with path.open("rb") as stream:
                        checkpoint = pickle.load(stream)
                    if (checkpoint["version"] != 2 or checkpoint["next_step"] != next_step
                            or checkpoint["seed"] != seed or checkpoint["epsilon"] != experiment["epsilon"]
                            or checkpoint["provenance"]["dataset_sha256"] != first["dataset_sha256"]
                            or set(checkpoint["assignment"]) != set(frame.index)):
                        raise ValueError("Checkpoint parameters or node coverage mismatch")
                    assignment = np.asarray([str(checkpoint["assignment"][i]) for i in frame.index])
                    if len(np.unique(assignment)) != experiment["districts"]:
                        raise ValueError("District count mismatch")
                    units, weighted = partition_distances(reference, assignment, population)
                    _, codes = np.unique(assignment, return_inverse=True)
                    plans.append({"codes": codes, "districts": len(np.unique(codes)), "seed": seed, "step": next_step - 1,
                                  "starting_plan": experiment["starting_plan"]})
                    snapshot_rows.append({"condition": condition, "seed": seed, "step": next_step - 1,
                                          "starting_plan": experiment["starting_plan"], "unit_vi_to_reference_bits": units,
                                          "population_vi_to_reference_bits": weighted})
                    checkpoint_count += 1
        pairs, size = [], len(plans)
        image = np.zeros((size, size))
        for i, left in enumerate(plans):
            for j in range(i + 1, size):
                right = plans[j]
                units, weighted = coded_distances(left["codes"], right["codes"], left["districts"], right["districts"], population)
                image[i, j] = image[j, i] = weighted
                lag = abs(left["step"] - right["step"])
                pairs.append({"condition": condition, "left_seed": left["seed"], "right_seed": right["seed"],
                              "left_step": left["step"], "right_step": right["step"], "step_lag": lag,
                              "lag_group": lag_group(lag), "same_chain": left["seed"] == right["seed"],
                              "same_starting_plan": left["starting_plan"] == right["starting_plan"],
                              "both_post_warmup": min(left["step"], right["step"]) >= first["warmup"],
                              "unit_vi_bits": units, "population_vi_bits": weighted})
        table = pd.DataFrame(pairs)
        pair_count += len(table)
        table.to_csv(args.output_dir / f"{condition}_pairs.csv", index=False, mode="x")
        for keys, part in table.groupby(["both_post_warmup", "same_chain", "same_starting_plan", "lag_group"]):
            row = dict(zip(("both_post_warmup", "same_chain", "same_starting_plan", "lag_group"), keys))
            row.update(condition=condition, pairs=len(part))
            for metric in ("unit_vi_bits", "population_vi_bits"):
                row[metric + "_mean"] = float(part[metric].mean())
                row[metric + "_q25"] = float(part[metric].quantile(0.25))
                row[metric + "_median"] = float(part[metric].median())
                row[metric + "_q75"] = float(part[metric].quantile(0.75))
            summaries.append(row)
        fig, ax = plt.subplots(figsize=(8, 7))
        plot = ax.imshow(image, origin="lower", interpolation="nearest", cmap="viridis")
        centers, labels = [], []
        for seed in sorted(seeds):
            indices = [i for i, plan in enumerate(plans) if plan["seed"] == seed]
            centers.append((indices[0] + indices[-1]) / 2); labels.append(str(seed))
            if indices[0]:
                ax.axvline(indices[0] - 0.5, color="white", linewidth=0.7)
                ax.axhline(indices[0] - 0.5, color="white", linewidth=0.7)
        ax.set_xticks(centers, labels, rotation=45)
        ax.set_yticks(centers, labels)
        ax.set_xlabel("Seed; checkpoints ordered by recorded step within each seed")
        ax.set_ylabel("Seed; checkpoints ordered by recorded step within each seed")
        ax.set_title(condition.replace("_", " ") + " | partition distance")
        fig.colorbar(plot, ax=ax, label="Population-weighted variation of information (bits)")
        fig.tight_layout()
        path = args.output_dir / f"{condition}_distances.png"
        fig.savefig(path, dpi=160);plt.close(fig)
        references.append({"condition": condition, "dataset": str(dataset.relative_to(ROOT)),
                           "dataset_sha256": first["dataset_sha256"], "units": len(frame),
                           "zero_population_units": int((population == 0).sum()), "checkpoints": size,
                           "reference_assignment": "CONG_DIST", "figure": path.name,
                           "figure_sha256": file_sha256(path)})
        print(condition, size, "checkpoints", len(table), "pairs", flush=True)
    pd.DataFrame(summaries).to_csv(args.output_dir / "distance_summary.csv", index=False, mode="x")
    pd.DataFrame(snapshot_rows).to_csv(args.output_dir / "reference_distances.csv", index=False, mode="x")
    report = {"manifest_sha256": file_sha256(args.manifest), "checkpoint_audit_sha256": file_sha256(args.checkpoint_audit),
              "analysis_code_sha256": file_sha256(__file__), "checkpoint_snapshots": checkpoint_count,
              "pair_comparisons": pair_count, "conditions": references,
              "measure": "VI = 2 H(A,B) - H(A) - H(B), log base 2; unit weights include every unit, population weights assign zero mass to zero-population units",
              "reference": "https://doi.org/10.1016/j.jmva.2006.11.013",
              "limitations": "Saved checkpoints are spaced 100 states apart. Pair comparisons share plans and are dependent; counts are not effective sample sizes. VI measures partition membership, not physical boundary displacement. These descriptive comparisons do not establish disconnected support or convergence."}
    with (args.output_dir / "partition_distances.json").open("x") as stream:
        json.dump(report, stream, indent=2, allow_nan=False);stream.write("\n")


if __name__ == "__main__":
    main()
