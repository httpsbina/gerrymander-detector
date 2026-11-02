"""Render source-backed election sensitivity and common-geography evidence."""

import argparse
import json
from pathlib import Path
import sys

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.chain.checkpoint_integrity import file_sha256


MODELS = ["president_2024", "attorney_general_2024", "governor_2024"]
COLORS = {"2023": "#315e91", "2025": "#d87930"}


def nc_bars(ax, data, normalized=False):
    x = np.arange(3)
    for offset, year in ((-0.18, "2023"), (0.18, "2025")):
        values = []
        for model in MODELS:
            result = data["models"][model][year]
            if normalized:
                result = result["normalized_to_presidential_statewide_share"]
            values.append(result["dem_modeled_seats"])
        bars = ax.bar(x + offset, values, 0.34, label=year + "-adopted plan", color=COLORS[year])
        ax.bar_label(bars, padding=3)
    ax.set_xticks(x, ["President", "Attorney general", "Governor"])
    ax.set_ylim(0, 14)


def style(ax):
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(alpha=0.15)
    ax.set_axisbelow(True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    for path in (args.audit_root, args.output_dir):
        path.resolve().relative_to(ROOT)
    args.output_dir.mkdir(parents=True, exist_ok=False)
    tx = json.loads((args.audit_root / "tx_election_sensitivity_v2.json").read_text())
    nc = json.loads((args.audit_root / "nc_election_sensitivity_v2.json").read_text())
    saved = []
    def save(fig, name):
        path = args.output_dir / name
        if path.exists():
            raise FileExistsError("Refusing existing source figure")
        fig.savefig(path, dpi=200)
        plt.close(fig)
        saved.append({"file": name, "sha256": file_sha256(path)})
    fig, axes = plt.subplots(1, 2, figsize=(11, 5), gridspec_kw={"width_ratios": [1, 1.5]})
    values = [tx["models"][model]["2025"]["dem_modeled_seats"] for model in ("president_2024", "us_senate_2024")]
    bars = axes[0].bar(["President", "U.S. Senate"], values, color=COLORS["2023"], width=0.55)
    axes[0].bar_label(bars, padding=3)
    axes[0].set_ylim(0, 38)
    axes[0].set_title("Texas PLANC2333 (38 districts)")
    axes[0].set_ylabel("Modeled Democratic-majority districts")
    nc_bars(axes[1], nc)
    axes[1].set_title("North Carolina (14 districts)")
    axes[1].legend(frameon=False, loc="upper left", fontsize=9)
    for ax in axes:
        style(ax)
        ax.set_xlabel("2024 statewide election")
    fig.suptitle("Election choice changes enacted-plan scores", fontsize=14, fontweight="bold", y=0.97)
    fig.text(0.06, 0.04, "RDH modeled block allocations and official block assignments.\nPresidential, Senate, attorney-general and gubernatorial election models are scored separately.", fontsize=9)
    fig.subplots_adjust(bottom=0.23, top=0.80, wspace=0.32)
    save(fig, "election_model_sensitivity.png")
    fig, axes = plt.subplots(1, 2, figsize=(11, 5), sharey=True)
    for ax, normalized in zip(axes, (False, True)):
        nc_bars(ax, nc, normalized)
        style(ax)
        ax.set_title("Common statewide support scenario" if normalized else "Unadjusted statewide elections")
    axes[0].set_ylabel("Modeled Democratic-majority districts")
    axes[0].legend(frameon=False, fontsize=9, loc="upper left")
    fig.suptitle("NC election sensitivity with and without statewide-support normalization", fontsize=13, fontweight="bold", y=0.97)
    fig.text(0.06, 0.04, "Uniform swing of district two-party shares to the presidential statewide share.\nSource: RDH modeled block allocations and official block assignments.", fontsize=9)
    fig.subplots_adjust(bottom=0.20, top=0.80, wspace=0.12)
    save(fig, "nc_election_normalization_sensitivity.png")
    units = gpd.read_file(args.audit_root / "nc_block_union_candidate/nc_block_union_candidate.gpkg")
    pieces = units.loc[units.PRECINCT_KEY == "ONSLOW-:-SW19"]
    if len(pieces) != 2 or int(pieces.BLOCK_COUNT.sum()) != 208 or int(pieces.TOTPOP.sum()) != 7450:
        raise ValueError("Onslow figure data do not match the audited split")
    fig = plt.figure(figsize=(8, 6))
    ax = fig.add_axes((0.05, 0.20, 0.58, 0.65))
    for district, color in (("01", COLORS["2025"]), ("03", COLORS["2023"])):
        pieces.loc[pieces.CONG_DIST_2025 == district].plot(ax=ax, color=color, edgecolor="white", linewidth=0.5)
    ax.set_axis_off()
    fig.suptitle("NC common geography: Onslow SW19", fontsize=15, fontweight="bold", y=0.96)
    fig.legend(handles=[Patch(color=COLORS["2025"], label="2025 district 1"),
                        Patch(color=COLORS["2023"], label="2025 district 3")],
               loc="upper left", bbox_to_anchor=(0.64, 0.84), frameon=False)
    fig.text(0.66, 0.56, "District 1\n131 blocks\nPopulation 4,853\n\nDistrict 3\n77 blocks\nPopulation 2,597", fontsize=10)
    fig.text(0.07, 0.065, "All 208 Census blocks retained; total population 7,450. Both pieces were in district 3 in 2023.\nSource: RDH/Census block geometry and official block-to-district assignments.", fontsize=9)
    save(fig, "nc_onslow_block_union.png")
    with (args.output_dir / "figure_manifest.json").open("x") as stream:
        json.dump({"research_ready": False, "plot_code_sha256": file_sha256(__file__), "figures": saved}, stream, indent=2)
        stream.write("\n")
    print(f"Rendered {len(saved)} source-audit figures")


if __name__ == "__main__":
    main()
