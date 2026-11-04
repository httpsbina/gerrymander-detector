"""Render checkpoint seat ranges against recorded statewide election shares."""

import io
import json
from pathlib import Path
from statistics import median

from paper.texas_outputs import sha


def values(result, scores):
    states = {}
    for state, data in result["results"].items():
        selected = [row for row in scores if row["state"] == state]
        expected = {(group, chain["seed"]): chain["checkpoints"]
                    for group, group_data in data["groups"].items() for chain in group_data["chains"]}
        actual = {}
        seen = set()
        for row in selected:
            key = (row["group"], row["seed"])
            identity = (*key, row["step"])
            if identity in seen or key not in expected:
                raise ValueError("Duplicate or unexpected checkpoint")
            seen.add(identity); actual[key] = actual.get(key, 0) + 1
        if actual != expected:
            raise ValueError("Checkpoint coverage differs from registered summary")
        elections = []
        for index, model in enumerate(data["models"]):
            dem, rep = (data["inventory"]["statewide_votes"][column] for column in model["columns"])
            if min(dem, rep) < 0 or dem + rep <= 0:
                raise ValueError("Invalid statewide vote totals")
            seats = [row[model["office"]] for row in selected]
            elections.append({"election": model["office"], "vote_columns": model["columns"],
                              "statewide_democratic_votes": dem, "statewide_republican_votes": rep,
                              "statewide_democratic_two_party_share": dem / (dem + rep),
                              "checkpoint_observations": len(seats), "neutral_minimum_seats": min(seats),
                              "neutral_median_seats": median(seats), "neutral_maximum_seats": max(seats),
                              "enacted_seats": {year: counts[index] for year, counts in data["enacted_seats"].items()}})
        states[state] = elections
    return states


def figure(state, elections):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import MaxNLocator, PercentFormatter

    fig, ax = plt.subplots(figsize=(10, 7.8))
    x = [row["statewide_democratic_two_party_share"] for row in elections]
    low = [row["neutral_minimum_seats"] for row in elections]
    high = [row["neutral_maximum_seats"] for row in elections]
    middle = [row["neutral_median_seats"] for row in elections]
    ax.vlines(x, low, high, color="#8b99a5", linewidth=2, alpha=0.8, label="Checkpoint minimum to maximum")
    ax.scatter(x, middle, marker="o", s=52, color="#176b94", zorder=3, label="Checkpoint median")
    styles = {"2023": ("x", "#b35b14"), "2025": ("D", "#952a72")}
    for year in elections[0]["enacted_seats"]:
        marker, color = styles[year]
        label = "PLANC2333" if state == "tx" else f"NC {year} plan"
        colors = {"facecolors": "none", "edgecolors": color} if marker == "D" else {"color": color}
        ax.scatter(x, [row["enacted_seats"][year] for row in elections], marker=marker,
                   s=68, **colors,
                   linewidths=1.6, zorder=4, label=label)
    # Numbered labels keep close election shares at their exact coordinates.
    annotations = []
    for number, (share, top) in enumerate(zip(x, high), 1):
        annotations.append(ax.annotate(str(number), (share, top), xytext=(0, 7),
                                      textcoords="offset points", ha="center", fontsize=9))
    ax.set_title(f"{'Texas' if state == 'tx' else 'North Carolina'}: checkpoint election scores")
    ax.set_xlabel("Statewide Democratic two-party vote share")
    ax.set_ylabel("Democratic-majority congressional districts")
    ax.xaxis.set_major_formatter(PercentFormatter(1))
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    ax.set_ylim(bottom=0, top=max(high + [max(row["enacted_seats"].values()) for row in elections]) + 3)
    ax.margins(x=0.12)
    ax.grid(axis="y", alpha=0.2)
    ax.legend(loc="upper left", fontsize=9)
    columns = [elections[offset::3] for offset in range(3)]
    for offset, column in enumerate(columns):
        labels = [f"{elections.index(row) + 1}. {row['election']}" for row in column]
        fig.text(0.08 + offset * 0.31, 0.025, "\n".join(labels), fontsize=8.5, va="bottom")
    fig.subplots_adjust(left=0.09, right=0.97, top=0.93, bottom=0.26)
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    occupied = []
    for annotation in sorted(annotations, key=lambda item: item.xy[0]):
        while any(annotation.get_window_extent(renderer).expanded(1.25, 1.15).overlaps(box) for box in occupied):
            horizontal, vertical = annotation.get_position()
            annotation.set_position((horizontal, vertical + 8))
        occupied.append(annotation.get_window_extent(renderer).expanded(1.25, 1.15))
    stream = io.BytesIO(); fig.savefig(stream, format="png", dpi=180, metadata={"Software": "Matplotlib"})
    plt.close(fig)
    return stream.getvalue()


def artifacts(root):
    directory = Path(root) / "paper/election-sensitivity"
    names = ["results.json", "checkpoint_scores.json", "assignment_validation.json"]
    manifest = json.loads((Path(root) / "paper/validation/nc-cleanroom-20261103/artifacts.json").read_text())["files"]
    fingerprints = {}
    for name in names:
        path = directory / name; key = str(path.relative_to(root)); fingerprints[key] = sha(path)
        if manifest[key] != fingerprints[key]: raise ValueError("Registered checkpoint scores changed")
    result = json.loads((directory / "results.json").read_text())
    validation = json.loads((directory / "assignment_validation.json").read_text())
    if validation["results_sha256"] != fingerprints["paper/election-sensitivity/results.json"]:
        raise ValueError("Checkpoint validation is stale")
    data = {"source_checksums": fingerprints,
            "states": values(result, json.loads((directory / "checkpoint_scores.json").read_text()))}
    figures = {f"figures/{'texas' if state == 'tx' else 'nc'}/responsiveness.png": figure(state, rows)
               for state, rows in data["states"].items()}
    return data, figures
