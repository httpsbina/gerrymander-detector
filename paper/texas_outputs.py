"""Derive Texas paper figures and tables from checksum-registered audits."""

from collections import Counter
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import re

METRICS = {"dem_seats": "Democratic seats", "efficiency_gap": "Efficiency gap",
           "cut_edges": "Cut edges", "mean_median": "Mean-median"}
GROUPS = {"tx_rebuild": "Baseline", "tx_dispersed": "Dispersed", "joint_texas": "Joint"}


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def checked_file(root, reference, receipts):
    name = reference["path"]
    if Path(name).is_absolute():
        raise ValueError("Paper input paths must be repository-relative")
    path = root / name
    path.resolve().relative_to(root.resolve())
    actual = sha(path)
    if actual != reference["sha256"]:
        raise ValueError(f"Registered paper input changed: {name}")
    if name in receipts and receipts[name] != actual:
        raise ValueError("Conflicting input fingerprints")
    receipts[name] = actual
    return path


def read_reference(root, reference, receipts):
    return json.loads(checked_file(root, reference, receipts).read_text())


def report_entries(report):
    values = {key: value for key, value in report["experiments"].items() if key in GROUPS}
    if "joint_texas" in report:
        values["joint_texas"] = report["joint_texas"]
    return values


def history_rows(registry, registered_root, receipts):
    rows = {}
    def add(group, steps, metric, value, path, role):
        key = (group, steps, metric)
        selected = {name: value[name] for name in ("rank_split_rhat", "bulk_ess", "tail_ess", "ess_screening_minimum")}
        if not all(math.isfinite(v) for v in selected.values()):
            raise ValueError("Unavailable historical primary diagnostic")
        if key in rows:
            if any(rows[key][name] != val for name, val in selected.items()):
                raise ValueError(f"Conflicting historical diagnostic: {key}")
            rows[key]["sources"].append(path)
        else:
            rows[key] = {"group": group, "states_per_chain": steps, "metric": metric,
                         **selected, "role": role, "sources": [path]}
    for reference in registry["historical_audits"]:
        report = read_reference(registered_root, reference, receipts)
        entries = report_entries(report)
        lengths = {}
        for key, entry in entries.items():
            if key == "joint_texas":
                continue
            sizes = {int(re.search(r"_next(\d+)\.pkl$", item["path"]).group(1)) for item in entry["checkpoints"]}
            if len(sizes) != 1:
                raise ValueError("Historical cohort has unequal endpoints")
            lengths[key] = sizes.pop()
        for key, entry in entries.items():
            if key == "joint_texas":
                if len(set(lengths.values())) != 1:
                    raise ValueError("Historical joint audit mixes lengths")
                steps = next(iter(lengths.values()))
            else:
                steps = lengths[key]
            for metric in METRICS:
                add(key, steps, metric, entry["diagnostics"][metric], reference["path"], reference.get("role", "recorded_audit"))
    for reference in registry["prefix_comparisons"]:
        report = read_reference(registered_root, reference, receipts)
        for item in report["metrics"]:
            for name, value in item.items():
                match = re.fullmatch(r"at_(\d+)", name)
                if match:
                    add(report["group"], int(match.group(1)), item["metric"], value,
                        reference["path"], "informational_prefix")
    return sorted(rows.values(), key=lambda row: (row["states_per_chain"], row["group"], list(METRICS).index(row["metric"])))


def collect(registry_path, source_root, selected=None, frozen=False):
    registry = json.loads(registry_path.read_text())
    registered_root = registry_path.resolve().parents[1]
    receipts = {str(registry_path.relative_to(registered_root)): sha(registry_path)}
    chosen = selected or registry["selected"]
    input_root = source_root if selected else registered_root
    manifest = read_reference(input_root, chosen["manifest"], receipts)
    report = read_reference(input_root, chosen["audit"], receipts)
    expected_manifest = chosen["manifest"].get("source_sha256", chosen["manifest"]["sha256"])
    if report["manifest_sha256"] != expected_manifest:
        raise ValueError("Selected audit and manifest do not match")
    if not selected:
        def normalized(value):
            if isinstance(value, str):return value.replace(str(source_root.resolve()) + "/", "")
            if isinstance(value, list):return [normalized(v) for v in value]
            if isinstance(value, dict):return {k: normalized(v) for k, v in value.items()}
            return value
        for field, copied in (("manifest", manifest), ("audit", report)):
            reference = chosen[field]
            original = read_reference(source_root, {"path": reference["source_path"], "sha256": reference["source_sha256"]}, receipts)
            if normalized(original) != copied:
                raise ValueError("Portable selected record differs from its execution source")
    if set(manifest["experiments"]) != {"tx_rebuild", "tx_dispersed"}:
        raise ValueError("Texas outputs require both starting cohorts")
    entries = report_entries(report)
    if set(entries) != set(GROUPS):
        raise ValueError("Missing Texas cohort or joint diagnostics")
    for key, entry in entries.items():
        if entry.get("integrity", entry.get("status")) not in ("pass", "computed"):
            raise ValueError("Selected audit failed integrity checks")
        if set(entry["diagnostics"]) != set(METRICS):
            raise ValueError("Missing selected primary metric")
        for value in entry["diagnostics"].values():
            if not value["all_finite"] or any(not math.isfinite(value[n]) for n in ("rank_split_rhat", "bulk_ess", "tail_ess")):
                raise ValueError("Selected primary diagnostic is unavailable")
    score_report = read_reference(registered_root, registry["enacted_block_score"], receipts)
    score = score_report
    for key in registry["enacted_score_pointer"]:
        score = score[key]
    plan = score_report["plans"][registry["enacted_score_pointer"][1]]
    if sum(row["dem_modeled_votes"] > row["rep_modeled_votes"] for row in plan["districts"]) != score:
        raise ValueError("Enacted block score does not match its district votes")
    groups, tail = {}, []
    for key, experiment in manifest["experiments"].items():
        for name, expected in manifest["source_code"].items():
            checked_file(source_root, {"path": name, "sha256": expected}, receipts)
        checked_file(source_root, {"path": experiment["dataset"], "sha256": experiment["dataset_sha256"]}, receipts)
        for reference in entries[key]["checkpoints"]:
            checked_file(source_root, reference, receipts)
        if "kernel_equivalence_file" in experiment:
            checked_file(source_root, {"path": experiment["kernel_equivalence_file"], "sha256": experiment["kernel_equivalence_sha256"]}, receipts)
        counters = {seed: Counter() for seed in experiment["seeds"]}
        next_steps = {seed: 0 for seed in counters}
        for item in sorted(entries[key]["files"], key=lambda item: item["path"]):
            path = checked_file(source_root, item, receipts)
            match = re.search(r"_seed(-?\d+)_steps(\d+)-(\d+)\.csv$", path.name)
            if not match or int(match.group(1)) not in counters:
                raise ValueError("Unconfigured chain file")
            seed = int(match.group(1))
            if next_steps[seed] != int(match.group(2)):
                raise ValueError("Missing or overlapping chain segment")
            with path.open() as stream:
                for row in csv.DictReader(stream):
                    step = int(row["step"])
                    if step != next_steps[seed] or int(row["seed"]) != seed:
                        raise ValueError("Missing, repeated or wrong-seed state")
                    if abs(float(row["epsilon"]) - experiment["epsilon"]) > 1e-10:
                        raise ValueError("Trace constraint mismatch")
                    if not all(math.isfinite(float(row[name])) for name in METRICS):
                        raise ValueError("Nonfinite trace value")
                    if not 0 <= float(row["max_abs_pop_dev"]) <= experiment["epsilon"] + 1e-10:
                        raise ValueError("Trace population constraint violation")
                    seats = int(row["dem_seats"])
                    if not 0 <= seats <= experiment["districts"]:
                        raise ValueError("Invalid seat count")
                    if step >= experiment["warmup"]:
                        counters[seed][seats] += 1
                    next_steps[seed] += 1
            if next_steps[seed] != int(match.group(3)) + 1:
                raise ValueError("Segment length differs from its filename")
        if set(next_steps.values()) != {experiment["steps"]}:
            raise ValueError("Selected histories do not cover the registered length")
        combined = Counter()
        for seed, counts in counters.items():
            combined.update(counts)
            n = sum(counts.values())
            if n != experiment["steps"] - experiment["warmup"] or not n:
                raise ValueError("Wrong retained-state count")
            tail.append({"group": key, "kind": "chain", "seed": seed, "retained_states": n,
                         "score_threshold": score, "states_at_or_below_score": sum(v for k, v in counts.items() if k <= score)})
        n = sum(combined.values())
        groups[key] = {"seeds": experiment["seeds"], "states_per_chain": experiment["steps"],
                       "warmup_per_chain": experiment["warmup"], "retained_states": n,
                       "mean_democratic_seats": sum(k * v for k, v in combined.items()) / n,
                       "histogram": dict(sorted(combined.items()))}
        tail.append({"group": key, "kind": "cohort", "seed": "", "retained_states": n,
                     "score_threshold": score, "states_at_or_below_score": sum(v for k, v in combined.items() if k <= score)})
    if len({(v["states_per_chain"], v["warmup_per_chain"]) for v in groups.values()}) != 1:
        raise ValueError("Selected cohorts have unequal analysis windows")
    tail.append({"group": "joint_texas", "kind": "joint", "seed": "",
                 "retained_states": sum(v["retained_states"] for v in groups.values()), "score_threshold": score,
                 "states_at_or_below_score": sum(row["states_at_or_below_score"] for row in tail if row["kind"] == "cohort")})
    history = history_rows(registry, registered_root, receipts)
    diagnostics = {key: entry["diagnostics"] for key, entry in entries.items()}
    steps = next(iter(groups.values()))["states_per_chain"]
    for group, values in diagnostics.items():
        for metric, value in values.items():
            match = next((row for row in history if (row["group"], row["states_per_chain"], row["metric"]) == (group, steps, metric)), None)
            if match:
                if any(match[n] != value[n] for n in ("rank_split_rhat", "bulk_ess", "tail_ess")):
                    raise ValueError("Selected and historical audit disagree")
            else:
                history.append({"group": group, "states_per_chain": steps, "metric": metric,
                                **{n: value[n] for n in ("rank_split_rhat", "bulk_ess", "tail_ess", "ess_screening_minimum")},
                                "role": "frozen" if frozen else "selected", "sources": [chosen["audit"]["path"]]})
    history.sort(key=lambda row: (row["states_per_chain"], row["group"], list(METRICS).index(row["metric"])))
    trends = {}
    for group in GROUPS:
        trends[group] = {}
        for metric in METRICS:
            points = [row for row in history if row["group"] == group and row["metric"] == metric]
            changes = [b["rank_split_rhat"] - a["rank_split_rhat"] for a, b in zip(points, points[1:])]
            trends[group][metric] = {"audit_lengths": [row["states_per_chain"] for row in points],
                "rhat_values": [row["rank_split_rhat"] for row in points],
                "rising_intervals": sum(delta > 0 for delta in changes),
                "falling_intervals": sum(delta < 0 for delta in changes),
                "net_rhat_change": points[-1]["rank_split_rhat"] - points[0]["rank_split_rhat"]}
    bins = sorted({score, *(int(k) for group in groups.values() for k in group["histogram"])})
    bins = list(range(min(bins), max(bins) + 1))
    return {"status": "frozen" if frozen else "provisional", "plan_label": registry["plan_label"],
            "enacted_democratic_seats": score, "groups": groups, "histogram_bins": bins,
            "tail_counts": tail, "selected_diagnostics": diagnostics, "diagnostic_history": history,
            "rhat_strict_upper": report["screening"]["rhat_strict_upper"],
            "trends": trends, "source_fingerprints": receipts, "selected_audit": chosen["audit"]["path"],
            "selected_manifest": chosen["manifest"]["path"]}


def csv_bytes(rows, fields):
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n", extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode()


def findings(data):
    groups = data["groups"]
    first = next(iter(groups.values()))
    lines = ["# Texas findings", "",
             f"- I used the first {first['states_per_chain']:,} recorded states per chain, retaining {sum(g['retained_states'] for g in groups.values()):,} states after {first['warmup_per_chain']:,} warmup states per chain.",
             f"- PLANC2333 scores {data['enacted_democratic_seats']} Democratic-majority districts under the modeled presidential votes, using the block-resolution audit."]
    for key, group in groups.items():
        row = next(r for r in data["tail_counts"] if r["group"] == key and r["kind"] == "cohort")
        lines.append(f"- I counted {row['states_at_or_below_score']:,} states at or below that score among {row['retained_states']:,} retained {GROUPS[key].lower()} states; the mean Democratic seat count is {group['mean_democratic_seats']:.5f}.")
    for key, values in data["selected_diagnostics"].items():
        failures = [f"{METRICS[metric]} (R-hat {value['rank_split_rhat']:.5f}, bulk ESS {value['bulk_ess']:.1f}, tail ESS {value['tail_ess']:.1f})"
                    for metric, value in values.items() if value['rank_split_rhat'] >= data['rhat_strict_upper'] or min(value['bulk_ess'], value['tail_ess']) < value['ess_screening_minimum']]
        lines.append(f"- I recorded these failing {GROUPS[key].lower()} primary screens: " + ("; ".join(failures) if failures else "none") + ".")
    for key, metrics in data["trends"].items():
        for metric in ("cut_edges", "mean_median"):
            trend = metrics[metric]
            lines.append(f"- I recorded {GROUPS[key].lower()} {METRICS[metric].lower()} R-hat from {trend['rhat_values'][0]:.5f} to {trend['rhat_values'][-1]:.5f} across {len(trend['audit_lengths'])} audit lengths, with {trend['rising_intervals']} rising intervals.")
    lines.extend(["", "## Limitations", "",
                  "I use modeled election allocations with the recorded ReCom population and contiguity constraints. The states are autocorrelated, and these counts are descriptive frequencies; zero observations do not imply zero probability. I have not established uniform sampling or full legal compliance."])
    return ("\n".join(lines) + "\n").encode()


def artifacts(data):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import StrMethodFormatter
    result = {}
    bins = data["histogram_bins"]
    edges = [v - .5 for v in bins] + [bins[-1] + .5]
    counts = {key: [group["histogram"].get(v, group["histogram"].get(str(v), 0)) for v in bins] for key, group in data["groups"].items()}
    first = next(iter(data["groups"].values()))
    colors = {"tx_rebuild": "#2166ac", "tx_dispersed": "#d95f02", "joint_texas": "#6a3d9a"}
    role = data["status"].capitalize()
    with plt.rc_context({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False}):
        fig, ax = plt.subplots(figsize=(9.5, 5.2))
        pooled = [sum(v[i] for v in counts.values()) for i in range(len(bins))]
        ax.bar(bins, pooled, width=.88, color="#d8d8d8", label="All chains", zorder=1)
        for key, values in counts.items():
            ax.stairs(values, edges, linewidth=2, color=colors[key], label=GROUPS[key], zorder=2)
        ax.axvline(data["enacted_democratic_seats"], color="#222222", linestyle="--", linewidth=1.5,
                   label=f"{data['plan_label']}: {data['enacted_democratic_seats']} seats", zorder=3)
        ax.set(xlabel="Democratic-majority districts under modeled presidential votes", ylabel="Retained states",
               title=f"{role} Texas: {first['states_per_chain']:,} recorded states per chain")
        ax.set_xticks(bins)
        ax.yaxis.set_major_formatter(StrMethodFormatter("{x:,.0f}"))
        ax.legend(frameon=False)
        ax.grid(axis="y", alpha=.18)
        fig.tight_layout()
        buffer = io.BytesIO();fig.savefig(buffer, format="png", dpi=240);plt.close(fig)
        result["figures/texas/seat_histogram.png"] = buffer.getvalue()
        fig, axes = plt.subplots(len(METRICS), 2, figsize=(11, 12), sharex=True)
        for i, metric in enumerate(METRICS):
            for key in GROUPS:
                rows = [row for row in data["diagnostic_history"] if row["group"] == key and row["metric"] == metric]
                for column, field in enumerate(("rank_split_rhat", "bulk_ess")):
                    axes[i, column].plot([r["states_per_chain"] for r in rows], [r[field] for r in rows],
                                         marker="o", markersize=3, color=colors[key], label=GROUPS[key])
            axes[i, 0].axhline(data["rhat_strict_upper"], color="#333333", linestyle=":", label="R-hat threshold")
            thresholds = sorted({values[metric]["ess_screening_minimum"] for values in data["selected_diagnostics"].values()})
            for threshold in thresholds:
                axes[i, 1].axhline(threshold, color="#555555", linestyle=":", label=f"ESS {threshold:g}")
            axes[i, 0].set_ylabel(f"{METRICS[metric]}\nR-hat")
            axes[i, 1].set_ylabel("Bulk ESS")
            for ax in axes[i]:
                ax.grid(alpha=.18)
                ax.xaxis.set_major_formatter(StrMethodFormatter("{x:,.0f}"))
        axes[0, 0].legend(frameon=False, fontsize=8)
        axes[0, 1].legend(frameon=False, fontsize=8)
        for ax in axes[-1]:ax.set_xlabel("Recorded states per chain")
        fig.suptitle(f"{role} Texas convergence across recorded audits", y=.995)
        fig.tight_layout()
        buffer = io.BytesIO();fig.savefig(buffer, format="png", dpi=200);plt.close(fig)
        result["figures/texas/convergence_history.png"] = buffer.getvalue()
    rows = [{"group": group, "metric": metric, **values} for group, metrics in data["selected_diagnostics"].items() for metric, values in metrics.items()]
    fields = ["group", "metric", "rank_split_rhat", "bulk_ess", "tail_ess", "mcse_mean", "mcse_sd", "mcse_q05", "mcse_q95", "ess_screening_minimum"]
    result["tables/texas/shared_diagnostics.csv"] = csv_bytes(rows, fields)
    result["tables/texas/tail_counts.csv"] = csv_bytes(data["tail_counts"], ["group", "kind", "seed", "retained_states", "score_threshold", "states_at_or_below_score"])
    result["tables/texas/convergence_history.csv"] = csv_bytes(data["diagnostic_history"], ["group", "states_per_chain", "metric", "rank_split_rhat", "bulk_ess", "tail_ess", "ess_screening_minimum", "role"])
    result["texas_findings.md"] = findings(data)
    return result
