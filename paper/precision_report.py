"""Render the numerical precision review for advisor discussion."""

import argparse
import csv
import json
from pathlib import Path

from paper.review_precision import METRICS, ROOT, sha


def display(value, metric):
    return f"{value * METRICS[metric][2]:.5f}"


def note(report):
    lines = ["# Frozen-run precision and stability review", "",
        "I reviewed the frozen NC23k and Texas70k histories, retaining the existing 500-state warmup, all chains and all later observations. I reproduced each recorded mean MCSE with the pinned ArviZ version, checked the stored first/last 1,000-state comparisons, and added post-warmup half comparisons and direct seat-tail indicators. I have left the new acceptance decisions pending; the freezes and primary screens are unchanged.", "",
        "## Mean precision", "",
        "Each cell gives the estimated mean followed by its MCSE in parentheses. Efficiency gap and median minus mean use percentage points; seats and cut edges keep their original units. The complete SD and quantile MCSE records are in `summary.csv` and `results.json`.", ""]
    for state, data in report["states"].items():
        names = data["cohorts"] + ["joint"]
        lines.extend([f"### {'North Carolina' if state == 'nc' else 'Texas'}", "",
                      "| Metric | " + " | ".join(names) + " |",
                      "| --- | " + " | ".join(["---:"] * len(names)) + " |"])
        for metric, (label, unit, scale) in METRICS.items():
            rows = [next(row for row in data["summary"] if row["group"] == group and row["metric"] == metric) for group in names]
            cells = [f"{display(row['mean'], metric)} ({display(row['mcse_mean'], metric)})" for row in rows]
            lines.append(f"| {label}, {unit} | " + " | ".join(cells) + " |")
        lines.append("")
    lines.extend(["I use mean-specific MCSE from ArviZ rather than reconstructing it from rank-normalized bulk ESS. The pinned implementation uses the sample SD divided by the square root of mean-specific ESS. MCSE measures simulation error in an estimated expectation; the spread of sampled plans is a separate quantity. The [diagnostic paper, sections 3.2 and 4.1](https://arxiv.org/html/1903.08008v5), explains that distinction.", "",
        "## Starting-map comparison", "",
        "I subtract the first cohort's mean from the second cohort's mean: NC 2025 minus NC 2023, and Texas dispersed minus baseline. I combine their MCSEs by the square root of the sum of squares because the chain groups use independent seeds. The resulting ratio is a descriptive precision comparison, with no rejection threshold applied.", "",
        "| State | Metric | Cohort difference | Combined MCSE | Difference / MCSE |",
        "| --- | --- | ---: | ---: | ---: |"])
    for state, data in report["states"].items():
        for row in data["independent_cohort_differences"]:
            metric = row["metric"]
            lines.append(f"| {state} | {METRICS[metric][0]} | {display(row['second_minus_first'], metric)} | {display(row['combined_mcse'], metric)} | {row['difference_over_combined_mcse']:.3f} |")
    lines.extend(["", "## Window and warmup comparisons", "",
        "I split each post-warmup history into contiguous halves and retain every observation. The table reports the joint second-half mean minus first-half mean, alongside each half's MCSE. The two halves belong to the same chains, so I report their MCSEs separately and do not use an independence-based test of their difference. `halves.csv` includes both cohorts as well as the joint group, and `chains.csv` retains every chain's half shift and the frozen first/last 1,000-state shift.", "",
        "| State | Metric | Half shift | First-half MCSE | Second-half MCSE | Largest individual-chain half shift | Seed |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |"])
    for state, data in report["states"].items():
        for row in data["halves"]:
            if row["group"] != "joint": continue
            metric = row["metric"]
            largest = max((chain for chain in data["chains"] if chain["metric"] == metric), key=lambda chain: abs(chain["half_difference"]))
            first = row["first_mcse_mean"]["value"]; second = row["second_mcse_mean"]["value"]
            lines.append(f"| {state} | {METRICS[metric][0]} | {display(row['second_minus_first'], metric)} | {display(first, metric) if first is not None else 'unavailable'} | {display(second, metric) if second is not None else 'unavailable'} | {display(largest['half_difference'], metric)} | {largest['seed']} |")
    lines.extend(["", "I also compare means after each recorded warmup choice with the registered 500-state result. The table gives the largest absolute mean shift among those choices; the full means and 5th/95th percentiles are in `warmups.csv`.", "",
        "| State | Metric | First cohort | Second cohort | Joint |",
        "| --- | --- | ---: | ---: | ---: |"])
    for state, data in report["states"].items():
        for metric in METRICS:
            shifts = [max(abs(row["difference_from_registered_warmup"]) for row in data["warmups"] if row["metric"] == metric and row["group"] == group) for group in data["cohorts"] + ["joint"]]
            lines.append(f"| {state} | {METRICS[metric][0]} | " + " | ".join(display(value, metric) for value in shifts) + " |")
    lines.extend(["", "The two running-mean figures use every stored audit window, weighted by its number of states. I draw each chain separately and mark its cohort's full retained-history mean with a dashed line. This keeps opposite chain movements visible when the joint mean changes little.", "",
        "## Seat-tail precision", "",
        "The recorded seat 5th/95th quantile MCSEs are zero. In the [quantile method, section 4.4](https://arxiv.org/html/1903.08008v5), uncertainty in a quantile's rank is mapped back to observed values; both endpoints can land on the same integer seat count. I therefore reviewed the separate binary event of scoring at or below each enacted presidential seat count.", "",
        "| State | Group | Score threshold | Events / retained states | Contiguous event runs | Frequency, % | MCSE, percentage points | Indicator R-hat |",
        "| --- | --- | ---: | --- | ---: | ---: | ---: | ---: |"])
    tail_rows = []
    for state, data in report["states"].items():
        for group, row in data["tail_indicator"].items():
            mcse = row["mcse_frequency"]["value"]; rhat = row["rank_split_rhat_indicator"]["value"]
            lines.append(f"| {state} | {group} | {row['threshold']} | {row['events']} / {row['observations']} | {sum(row['event_runs_by_chain'])} | {100 * row['frequency']:.6f} | {100 * mcse:.6f} | {rhat:.6f} |" if mcse is not None and rhat is not None else f"| {state} | {group} | {row['threshold']} | {row['events']} / {row['observations']} | {sum(row['event_runs_by_chain'])} | {100 * row['frequency']:.6f} | unavailable | unavailable |")
            for seed, count, runs, n in zip(row["seeds"], row["events_by_chain"], row["event_runs_by_chain"], row["retained_by_chain"]):
                tail_rows.append({"state": state, "group": group, "seed": seed, "threshold": row["threshold"], "events": count, "event_runs": runs, "observations": n})
    for state, data in report["states"].items():
        row = data["tail_indicator"]["joint"]; error = row["mcse_frequency"]["value"]
        if error is not None and row["frequency"] > 0:
            lines.extend(["", f"I estimate a relative MCSE of {100 * error / row['frequency']:.2f}% for the joint {state} tail frequency. Its {row['events']} event states occur in {sum(row['event_runs_by_chain'])} contiguous runs, which I keep as descriptive episode counts."])
    lines.extend(["", "## Decisions for review", "",
        "I need to choose the paper's estimands and acceptable Monte Carlo error in their own units with Dr. Gerber, including whether the rare-event frequency is a numerical finding or only a descriptive count. I also need an agreed way to assess the observed window shifts and cohort differences against that precision budget. I have not assigned new tolerances or marked these comparisons as accepted. Any acceptance criteria will be recorded before they are used, with the existing freezes kept as the historical record.", "",
        "## Reproducing", "", "```sh",
        "nice -n 15 env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 MPLCONFIGDIR=\"$PWD/.venv/matplotlib\" .venv/science/bin/python -m paper.review_precision --source-root . --output-dir paper/reviews/NEW_REVIEW_DIRECTORY",
        "nice -n 15 env MPLCONFIGDIR=\"$PWD/.venv/matplotlib\" .venv/science/bin/python -m paper.precision_report --results paper/reviews/NEW_REVIEW_DIRECTORY/results.json",
        "```", "",
        "`results.json` records the full values, software versions, frozen-input checksums and diagnostic availability. The CSVs retain every metric, cohort and chain. `artifacts.json` records the output checksums. The MCSE definitions also follow the [mean](https://mc-stan.org/posterior/reference/mcse_mean.html) and [quantile](https://mc-stan.org/posterior/reference/mcse_quantile.html) estimands documented by the posterior package; all numerical calculations here use the pinned ArviZ implementation.", "",
        "## Limitations", "",
        "I use finite, autocorrelated simulations under the recorded ReCom constraints and modeled block votes. MCSE conditions on the sampled regime and does not include data/model uncertainty or undetected nonstationarity. Rare-event indicator R-hat can remain close to one with sparse events; a chain with no events gives limited information about unseen tails. Contiguous event runs are dependent observations, and zero observed events leave nonzero probabilities possible. These tail frequencies describe the implemented ensemble and are not calibrated p-values. The within-chain half comparisons are descriptive, and the stored NC windows include a shorter final window. This review leaves MCSE and stability acceptance pending, together with the earlier geographic, sampling-distribution and legal-model limitations.", ""])
    return "\n".join(lines), tail_rows


def cumulative_window_points(windows, group, seed, metric):
    rows = sorted((row for row in windows if row["experiment"] == group and int(row["seed"]) == seed), key=lambda row: int(row["first_step"]))
    states, means, total, accumulated = [], [], 0, 0.0
    previous = None
    for row in rows:
        first, last, count = (int(row[name]) for name in ["first_step", "last_step", "states"])
        if count != last - first + 1 or (previous is not None and first != previous + 1):
            raise ValueError("Missing or overlapping recorded windows")
        accumulated += float(row[metric + "_mean"]) * count; total += count
        states.append(last + 1); means.append(accumulated / total); previous = last
    if not rows: raise ValueError("Missing recorded windows")
    return states, means


def plot_windows(state, data, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import StrMethodFormatter

    fig, axes = plt.subplots(4, 2, figsize=(12, 11), sharex=True)
    for column, group in enumerate(data["cohorts"]):
        seeds = sorted({int(row["seed"]) for row in data["recorded_windows"] if row["experiment"] == group})
        for index, (metric, (label, unit, scale)) in enumerate(METRICS.items()):
            ax = axes[index, column]
            for seed in seeds:
                states, means = cumulative_window_points(data["recorded_windows"], group, seed, metric)
                expected = next(row["mean"] for row in data["chains"] if row["group"] == group and row["seed"] == seed and row["metric"] == metric)
                if abs(means[-1] - expected) > 1e-10: raise ValueError("Running mean does not reproduce frozen chain mean")
                ax.plot(states, [scale * value for value in means], linewidth=1.1, label=str(seed))
            full = next(row for row in data["summary"] if row["group"] == group and row["metric"] == metric)
            ax.axhline(scale * full["mean"], color="black", linestyle="--", linewidth=1, label="Full cohort mean")
            ax.set_ylabel(f"{label}\n{unit}"); ax.grid(alpha=.18)
            ax.xaxis.set_major_formatter(StrMethodFormatter("{x:,.0f}"))
            if index == 0: ax.set_title(group); ax.legend(fontsize=7, ncol=2, frameon=False)
    for ax in axes[-1]: ax.set_xlabel("Recorded states per chain")
    fig.suptitle(f"{'North Carolina' if state == 'nc' else 'Texas'}: cumulative means from stored post-warmup windows")
    fig.tight_layout(rect=(0, 0, 1, .96)); fig.savefig(path, dpi=180); plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("--results", type=Path, required=True)
    args = parser.parse_args(); source = args.results.resolve(); source.relative_to(ROOT); directory = source.parent
    report = json.loads(source.read_text()); text, tails = note(report)
    names = ["README.md", "tail_counts.csv", "artifacts.json", *[state + "_running_means.png" for state in report["states"]]]
    if any((directory / name).exists() for name in names): raise FileExistsError("Existing precision-review render")
    (directory / "README.md").write_text(text)
    with (directory / "tail_counts.csv").open("x", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(tails[0]), lineterminator="\n"); writer.writeheader(); writer.writerows(tails)
    for state, data in report["states"].items(): plot_windows(state, data, directory / (state + "_running_means.png"))
    manifest = {"command": "python -m paper.precision_report --results " + str(source.relative_to(ROOT)),
                "files": {str(path.relative_to(directory)): sha(path) for path in directory.iterdir() if path.is_file()},
                "code": {name: sha(ROOT / name) for name in ["paper/review_precision.py", "paper/precision_report.py"]}}
    (directory / "artifacts.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__": main()
