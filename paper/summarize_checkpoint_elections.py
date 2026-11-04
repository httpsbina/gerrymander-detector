"""Build election sensitivity tables from verified checkpoint scores."""

import argparse
import csv
import json
from pathlib import Path

from paper.score_checkpoint_elections import sha


def summary_rows(result):
    rows = []
    for state, data in result["results"].items():
        for index, model in enumerate(data["models"]):
            selections = dict(data["groups"])
            groups = list(selections.values())
            count = sum(group["checkpoints"] for group in groups)
            selections["joint"] = {"checkpoints": count,
                "mean_democratic_seats": [sum(group["mean_democratic_seats"][i] * group["checkpoints"]
                                               for group in groups) / count for i in range(len(data["models"]))],
                "at_or_below_enacted": {year: [sum(group["at_or_below_enacted"][year][i] for group in groups)
                                                for i in range(len(data["models"]))] for year in data["enacted_seats"]}}
            for group, values in selections.items():
                for year, enacted in data["enacted_seats"].items():
                    rows.append({"state": state, "election": model["office"], "group": group,
                                 "checkpoints": values["checkpoints"],
                                 "mean_democratic_seats": values["mean_democratic_seats"][index],
                                 "enacted_year": year, "enacted_democratic_seats": enacted[index],
                                 "checkpoints_at_or_below_enacted": values["at_or_below_enacted"][year][index]})
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, required=True)
    args = parser.parse_args()
    directory = args.results.parent
    validation = json.loads((directory / "assignment_validation.json").read_text())
    if validation["results_sha256"] != sha(args.results): raise ValueError("Validated results changed")
    result = json.loads(args.results.read_text()); rows = summary_rows(result)
    for name in ("summary.json", "summary.csv", "README.md"):
        if (directory / name).exists(): raise FileExistsError(directory / name)
    (directory / "summary.json").write_text(json.dumps({"source_results_sha256": sha(args.results), "rows": rows}, indent=2) + "\n")
    with (directory / "summary.csv").open("x", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader(); writer.writerows(rows)
    lines = ["# Checkpoint election sensitivity", "",
             "I scored the saved assignments with every other statewide Democratic-versus-Republican contest in the local 2024 block files, including judicial elections. I also rescored the presidential vote as a check against the chain CSVs. I kept the original vote magnitudes, with no statewide normalization or uniform swing.", "",
             "I used Texas's shared 45,000-state history and NC's frozen 23,000-state history, scoring every checkpoint saved at a 100-state boundary after the existing warmup. A checkpoint at next step N contains recorded state N-1. I count checkpoint observations, including revisited assignments, rather than distinct maps.", ""]
    for state in result["results"]:
        lines.extend([f"## {'Texas' if state == 'tx' else 'North Carolina'}", "",
                      "| Election | Mean Democratic seats | Enacted year | Enacted seats | At or below enacted | Checkpoints |",
                      "| --- | ---: | --- | ---: | ---: | ---: |"])
        for row in rows:
            if row["state"] == state and row["group"] == "joint":
                lines.append(f"| {row['election']} | {row['mean_democratic_seats']:.5f} | {row['enacted_year']} | {row['enacted_democratic_seats']} | {row['checkpoints_at_or_below_enacted']} | {row['checkpoints']} |")
        lines.append("")
    lines.extend(["## Reproducing", "", "```sh",
                  "nice -n 15 env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 .venv/science/bin/python -m paper.score_checkpoint_elections --source-root . --output-dir paper/NEW_ELECTION_DIRECTORY",
                  "nice -n 15 env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 .venv/science/bin/python -m paper.validate_checkpoint_elections --source-root . --results paper/NEW_ELECTION_DIRECTORY/results.json",
                  "nice -n 15 .venv/science/bin/python -m paper.summarize_checkpoint_elections --results paper/NEW_ELECTION_DIRECTORY/results.json", "```", "",
                  "`results.json` contains the block coverage, statewide totals, cohort and chain summaries, seeds, source hashes and checkpoint hashes. `checkpoint_scores.json` records every scored assignment. `summary.csv` and `summary.json` contain both cohort and joint comparisons. `assignment_validation.json` checks the graph, checkpoint provenance and plan fingerprints against the simulation inputs. I score Texas PLANC2333 and both NC enacted plans directly from their block assignments.", "",
                  "## Limitations", "",
                  "I use RDH's modeled block allocations, and these scores inherit their precinct membership and allocation uncertainty. The eight previously recorded Texas precinct overlap pairs remain unresolved. Democratic seats mean strict Democratic majorities of the two-party vote; third-party votes are excluded. The checkpoints are autocorrelated, so the counts are descriptive frequencies, with zero observations leaving nonzero probabilities possible. Texas still fails its convergence screens, and the NC freeze covers the original presidential metrics rather than these additional election scores. The implemented ReCom ensemble is not established as uniform or fully legally constrained. I exclude district-only races and NC's nonpartisan referendum because they do not provide statewide Democratic-versus-Republican votes.", ""])
    (directory / "README.md").write_text("\n".join(lines))


if __name__ == "__main__":
    main()
