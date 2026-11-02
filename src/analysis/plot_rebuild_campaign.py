"""Render complete-chain traces and pooled-rank comparisons without thinning."""

import argparse
import json
from pathlib import Path
from types import SimpleNamespace
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import rankdata

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.analysis.audit_ensemble_chains import load_chain
from src.chain.checkpoint_integrity import file_sha256

LABELS = {
    "dem_seats": "Democratic-majority districts",
    "efficiency_gap": "GerryChain efficiency gap",
    "cut_edges": "Cut edges",
    "mean_median": "Democratic median minus mean share",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--experiments", nargs="+")
    args = parser.parse_args()
    for path in (args.manifest, args.output_dir):
        path.resolve().relative_to(ROOT)
    if args.output_dir.exists():
        raise FileExistsError("Refusing existing trace/rank figure directory")
    manifest = json.loads(args.manifest.read_text())
    selected = args.experiments or list(manifest["experiments"])
    if set(selected) - set(manifest["experiments"]):
        raise ValueError("Unknown experiment")
    args.output_dir.mkdir(parents=True, exist_ok=False)
    provenance = {"research_ready": False, "manifest_sha256": file_sha256(args.manifest), "figures": []}
    plot_groups = {}
    for key in selected:
        experiment = manifest["experiments"][key]
        directory = (ROOT / experiment["input_dir"]).resolve()
        directory.relative_to(ROOT)
        definition = SimpleNamespace(input_dir=directory, prefix=experiment["prefix"],
                                     epsilon=experiment["epsilon"], steps=experiment["steps"],
                                     districts=experiment["districts"])
        chains = {seed: load_chain(definition, seed) for seed in experiment["seeds"]}
        plot_groups[key] = (experiment, chains)
    for geometry in ("nc_block_union", "nc_precinct_sensitivity", "nc_population_sensitivity"):
        keys = [geometry + "_2023", geometry + "_2025"]
        if all(key in plot_groups for key in keys):
            left, right = [plot_groups[key] for key in keys]
            if any(left[0][name] != right[0][name] for name in (
                "dataset_sha256", "epsilon", "node_repeats", "steps", "warmup")):
                raise ValueError("Cannot plot incompatible NC groups jointly")
            if set(left[1]) & set(right[1]):
                raise ValueError("NC joint plots require distinct seeds")
            plot_groups[geometry + "_joint"] = (left[0], {**left[1], **right[1]})
    for key, (experiment, chains) in plot_groups.items():
        warmup = experiment["warmup"]
        for mode in ("trace", "rank"):
            fig, axes = plt.subplots(2, 2, figsize=(11, 7))
            for ax, metric in zip(axes.flat, LABELS):
                if mode == "trace":
                    for seed, chain in chains.items():
                        ax.plot(chain.step, chain[metric], linewidth=0.6, alpha=0.65, label=f"seed {seed}")
                    ax.axvspan(0, warmup, color="gray", alpha=0.12)
                    ax.axvline(warmup, color="gray", linewidth=0.7, linestyle="--")
                    ax.set_xlabel("Recorded state (all states shown)")
                    ax.set_ylabel(LABELS[metric])
                else:
                    samples = np.stack([chain.iloc[warmup:][metric].to_numpy(float) for chain in chains.values()])
                    if not np.isfinite(samples).all():
                        raise ValueError("Nonfinite rank-plot input")
                    pooled = rankdata(samples.ravel(), method="average").reshape(samples.shape)
                    edges = np.linspace(0, samples.size + 1, 21)
                    for index, seed in enumerate(chains):
                        ax.hist(pooled[index], bins=edges, weights=np.ones(samples.shape[1]) / samples.shape[1],
                                histtype="step", linewidth=1.2, label=f"seed {seed}")
                    ax.set_xlabel("Pooled average rank after configured warmup")
                    ax.set_ylabel("Fraction of each chain in rank bin")
                    ax.set_title(LABELS[metric], fontsize=10)
                ax.spines[["top", "right"]].set_visible(False)
                ax.grid(alpha=0.12)
            axes[0, 0].legend(frameon=False, fontsize=8)
            fig.suptitle(key.replace("_", " ") + f" | {mode} diagnostics", fontsize=13, fontweight="bold")
            caption = ("Gray region: configured warmup. All recorded states are shown."
                       if mode == "trace" else
                       "Post-warmup pooled ranks, with average ranks for ties; discrete seat counts leave empty bins.")
            fig.text(0.05, 0.025, caption, fontsize=8)
            fig.tight_layout(rect=(0, 0.07, 1, 0.94))
            path = args.output_dir / f"{key}_{mode}.png"
            if path.exists():
                raise FileExistsError("Refusing existing figure")
            fig.savefig(path, dpi=170)
            plt.close(fig)
            provenance["figures"].append({"path": str(path), "sha256": file_sha256(path)})
    with (args.output_dir / "figure_manifest.json").open("x") as stream:
        json.dump(provenance, stream, indent=2)
        stream.write("\n")
    print(f"Rendered {len(provenance['figures'])} diagnostic figures; research-ready: NO")


if __name__ == "__main__":
    main()
