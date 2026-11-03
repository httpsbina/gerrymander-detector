"""Export paper artifacts without changing frozen inputs or numerical results."""

import argparse
import csv
from datetime import datetime
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
LABELS = {"dem_seats": "Democratic-majority districts", "efficiency_gap": "Efficiency gap",
          "cut_edges": "Cut edges", "mean_median": "Mean-median"}
FIELDS = ("rank_split_rhat", "bulk_ess", "tail_ess", "mcse_mean", "mcse_sd", "mcse_q05", "mcse_q95", "ess_screening_minimum")


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def json_bytes(value):
    return formatted((json.dumps(value, indent=2, allow_nan=False) + "\n").encode(), "results.json")


def formatted(data, filename):
    prettier = ROOT / ".venv/formatting/node_modules/prettier/bin/prettier.cjs"
    if prettier.is_file():
        return subprocess.check_output(["node", str(prettier), "--stdin-filepath", filename], input=data)
    return data


def publish(path, data):
    if path.exists():
        if path.read_bytes() != data:
            raise FileExistsError(f"Existing paper artifact differs: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(data)


def merge_results(previous, current):
    for state, values in previous.items():
        if state == "_paper":
            continue
        if state not in current or values != current[state]:
            raise ValueError(f"Existing frozen paper numbers changed: {state}")
        if previous["_paper"][state] != current["_paper"][state]:
            raise ValueError(f"Existing frozen paper metadata changed: {state}")
    return current


def state_metadata(frozen, raw, root):
    manifest = json.loads((root / frozen["manifest"]).read_text())
    groups = {}
    for key, experiment in manifest["experiments"].items():
        initial = []
        directory = root / experiment["input_dir"]
        tag = f"{experiment['epsilon']:g}".replace(".", "p")
        for seed in experiment["seeds"]:
            files = sorted(directory.glob(f"{experiment['prefix']}_chain_eps{tag}_seed{seed}_steps*.csv"))
            with files[0].open() as stream:
                row = next(csv.DictReader(stream))
            if int(row["step"]) != 0:
                raise ValueError("Missing initial recorded state")
            initial.append(int(row["dem_seats"]))
        if len(set(initial)) != 1:
            initial_score = dict(zip(map(str, experiment["seeds"]), initial))
        else:
            initial_score = initial[0]
        groups[key] = {"starting_plan": experiment["starting_plan"], "seeds": experiment["seeds"],
                       "states_per_chain": experiment["steps"], "warmup_per_chain": experiment["warmup"],
                       "initial_democratic_majority_districts": initial_score}
    display = {group: {metric: {"rhat": f"{value['rank_split_rhat']:.5f}",
                               "bulk_ess": f"{value['bulk_ess']:.1f}", "tail_ess": f"{value['tail_ess']:.1f}",
                               "mcse_mean": f"{value['mcse_mean']:.8f}"}
                      for metric, value in metrics.items()} for group, metrics in raw["primary_diagnostics"].items()}
    screening = json.loads((root / frozen["audit_dir"] / "diagnostics.json").read_text())["screening"]
    return {"groups": groups, "screening": screening, "chains": len(raw["chain_summary"]),
            "recorded_states": sum(row["states"] for row in raw["chain_summary"]),
            "retained_states": sum(row["retained_states"] for row in raw["chain_summary"]), "display": display}


def findings(raw, metadata):
    rows = raw["chain_summary"]
    lines = ["# North Carolina findings", "",
             f"- I ran {metadata['chains']} chains, recording {metadata['recorded_states']:,} states and retaining {metadata['retained_states']:,} after warmup.",
             f"- I recorded {rows[0]['states']:,} states per chain and used {rows[0]['warmup']:,} warmup states, leaving {rows[0]['retained_states']:,} per chain."]
    for group, details in metadata["groups"].items():
        seeds = ", ".join(map(str, details["seeds"]))
        lines.append(f"- I started {group} from the {details['starting_plan']} assignment with seeds {seeds}; its initial map has {details['initial_democratic_majority_districts']} Democratic-majority districts under the presidential vote model.")
    lines.extend(["", "| Group | Metric | R-hat | Bulk ESS | Tail ESS |", "| --- | --- | ---: | ---: | ---: |"])
    for group, metrics in metadata["display"].items():
        for metric, values in metrics.items():
            lines.append(f"| {group} | {LABELS[metric]} | {values['rhat']} | {values['bulk_ess']} | {values['tail_ess']} |")
    joint = raw["primary_diagnostics"]["joint"]
    lines.extend(["", f"- I recorded joint seat-count mean MCSE of {joint['dem_seats']['mcse_mean']:.8f}; the full precision is in `results.json`.",
                  "", "## Limitations", "",
                  "- I use modeled presidential votes; sampler uniformity and full legal compliance remain outside the implemented model."])
    return formatted(("\n".join(lines) + "\n").encode(), "nc_findings.md")


def export(build, registry, destination, root=ROOT):
    reproduced = json.loads((build / "results.json").read_text())
    result, metadata, artifacts = {}, {}, {}
    for state, freeze_name in registry.items():
        freeze_path = root / freeze_name
        freeze_path.resolve().relative_to(root)
        frozen = json.loads(freeze_path.read_text())
        if frozen["state"] != state or frozen["status"] != "primary_convergence_frozen":
            raise ValueError("Only registered frozen states can be exported")
        original = json.loads((freeze_path.parent / "results.json").read_text())
        if reproduced[state] != original:
            raise ValueError(f"Reproduced numbers differ: {state}")
        for name, expected in frozen["checksums"].items():
            source = root / name
            source.resolve().relative_to(root)
            if sha(source) != expected:
                raise ValueError(f"Frozen input differs: {name}")
        result[state] = original
        metadata[state] = state_metadata(frozen, original, root)
        metadata[state]["freeze_manifest_sha256"] = sha(freeze_path)
        figures = sorted((build / state / "figures").glob("*.png"))
        expected_figures = sorted((root / frozen["figures_dir"]).glob("*.png"))
        if not figures or [p.name for p in figures] != [p.name for p in expected_figures]:
            raise ValueError(f"Missing frozen figures: {state}")
        for path in figures:
            original_path = root / frozen["figures_dir"] / path.name
            if sha(path) != sha(original_path):
                raise ValueError(f"Regenerated figure differs: {path.name}")
            artifacts[Path("figures") / state / path.name] = path.read_bytes()
        tables = sorted((build / state / "audit").glob("*.csv"))
        if not tables or [p.name for p in tables] != [p.name for p in sorted((root / frozen["audit_dir"]).glob("*.csv"))]:
            raise ValueError(f"Missing frozen tables: {state}")
        for path in tables:
            artifacts[Path("tables") / state / path.name] = path.read_bytes()
        buffer = io.StringIO(newline="")
        writer = csv.DictWriter(buffer, fieldnames=["group", "metric", *FIELDS], lineterminator="\n")
        writer.writeheader()
        for group, metrics in original["primary_diagnostics"].items():
            for metric, values in metrics.items():
                writer.writerow({"group": group, "metric": metric, **{field: values[field] for field in FIELDS}})
        artifacts[Path("tables") / state / "primary_diagnostics.csv"] = buffer.getvalue().encode()
        if state == "nc":
            artifacts[Path("nc_findings.md")] = findings(original, metadata[state])
    result["_paper"] = metadata
    results_path = destination / "results.json"
    if results_path.exists():
        merge_results(json.loads(results_path.read_text()), result)
    for name, data in artifacts.items():
        path = destination / name
        if path.exists() and path.read_bytes() != data:
            raise FileExistsError(f"Existing paper artifact differs: {name}")
    for name, data in artifacts.items():
        publish(destination / name, data)
    # This aggregate index may acquire a newly frozen state; prior state values stay identical.
    results_path.write_bytes(json_bytes(result))
    receipts = {str(name): sha(destination / name) for name in sorted(artifacts)}
    receipts["results.json"] = sha(results_path)
    record = {"command": "python -m paper.export", "frozen_states": list(registry),
              "freeze_manifests": registry, "files": receipts}
    (destination / "artifacts.json").write_bytes(json_bytes(record))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=Path("configs/paper_freezes.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("paper"))
    parser.add_argument("--build-dir", type=Path)
    args = parser.parse_args()
    for path in (args.registry, args.output_dir):
        path.resolve().relative_to(ROOT)
    if args.build_dir is None:
        stamp = datetime.now(ZoneInfo("America/New_York")).strftime("%Y%m%d-%H%M%S-%f")
        args.build_dir = Path(".venv/paper-build") / stamp
    args.build_dir.resolve().relative_to(ROOT)
    args.build_dir.parent.mkdir(parents=True, exist_ok=True)
    registry = json.loads(args.registry.read_text())
    if not registry:
        raise ValueError("No frozen states are registered")
    env = dict(os.environ, MPLCONFIGDIR=str(ROOT / ".venv/matplotlib"))
    command = [sys.executable, str(ROOT / "reproduce_paper.py"), "--registry", str(args.registry),
               "--output-dir", str(args.build_dir)]
    subprocess.run(command, cwd=ROOT, env=env, check=True)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    export(args.build_dir.resolve(), registry, args.output_dir.resolve())


if __name__ == "__main__":
    main()
