"""Export complete continuation boundaries without environment credentials."""

import argparse
import copy
import json
from pathlib import Path
import shutil

from src.chain.benchmark_baselines import checkpoint_path
from src.chain.checkpoint_integrity import file_sha256

ROOT = Path(__file__).resolve().parents[2]


def export(manifest_paths, destination):
    destination = destination.resolve()
    destination.relative_to(ROOT)
    destination.mkdir(parents=True, exist_ok=False)
    manifests = [json.loads(path.read_text()) for path in manifest_paths]
    source = manifests[0]["source_code"]
    if any(m["source_code"] != source for m in manifests):
        raise ValueError("Cannot export differing sampler profiles")
    experiments = {}
    for manifest in manifests:
        for key, value in manifest["experiments"].items():
            if key in experiments:
                raise ValueError("Duplicate exported experiment")
            experiments[key] = copy.deepcopy(value)
    def copy_file(path):
        path = ROOT / path
        path.resolve().relative_to(ROOT)
        relative = path.relative_to(ROOT)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            if file_sha256(path) != file_sha256(target):
                raise ValueError("Conflicting exported file")
        else:
            shutil.copyfile(path, target)
    for path in ROOT.joinpath("src").rglob("*.py"):
        copy_file(path)
    for name in ("main.py", "requirements-research-macos-arm64-py312.txt", "docs/freeze_rule.md"):
        copy_file(Path(name))
    if (ROOT / "configs/paper_freezes.json").exists():
        for name in ("configs/paper_freezes.json", "results.json", "reproduce_paper.py"):
            copy_file(Path(name))
        for name in json.loads((ROOT / "configs/paper_freezes.json").read_text()).values():
            frozen = json.loads((ROOT / name).read_text())
            for filename, expected in frozen["checksums"].items():
                if file_sha256(ROOT / filename) != expected:
                    raise ValueError("Frozen input changed before transfer")
                copy_file(Path(filename))
            copy_file(Path(name))
    (destination / "transfer_configs").mkdir()
    for key, e in experiments.items():
        copy_file(Path(e["dataset"]))
        directory = ROOT / e["input_dir"]
        covered = {seed: [] for seed in e["seeds"]}
        tag = f"{e['epsilon']:g}".replace(".", "p")
        import re
        for seed in e["seeds"]:
            prefix = f"{e['prefix']}_chain_eps{tag}_seed{seed}_steps"
            for path in directory.glob(prefix + "*.csv"):
                match = re.fullmatch(re.escape(prefix) + r"(\d+)-(\d+)\.csv", path.name)
                if match is None:
                    raise ValueError("Unexpected segment filename")
                first, last = map(int, match.groups())
                if last >= e["steps"]:
                    if first < e["steps"]:
                        raise ValueError("Transfer boundary splits a CSV segment")
                    continue
                covered[seed].append((first, last))
                copy_file(path)
            next_step = 0
            for first, last in sorted(covered[seed]):
                if first != next_step:
                    raise ValueError("Transfer history has missing or overlapping steps")
                next_step = last + 1
            if next_step != e["steps"]:
                raise ValueError("Incomplete transfer history")
            config_path = e.get("seed_configs", {}).get(str(seed), e["config"])
            registry = json.loads((ROOT / config_path).read_text())
            plan = registry["states"][e["state"]]["plans"][e["starting_plan"]]
            for step in (e["steps"] - 100, e["steps"]):
                if step <= 0:
                    raise ValueError("At least 100 prior recorded states required for replay")
                name = checkpoint_path(Path(), e, seed, step).name
                candidates = [directory.parent / "checkpoints" / name, ROOT / plan["checkpoint_dir"] / name]
                available = [p for p in candidates if p.is_file()]
                if not available or len({file_sha256(p) for p in available}) != 1:
                    raise ValueError("Missing or conflicting continuation checkpoint")
                target = destination / e["input_dir"]
                target = target.parent / "checkpoints" / name
                target.parent.mkdir(parents=True, exist_ok=True)
                if not target.exists():
                    shutil.copyfile(available[0], target)
            plan["output_dir"] = e["input_dir"]
            plan["checkpoint_dir"] = str(Path(e["input_dir"]).parent / "checkpoints")
            path = Path("transfer_configs") / f"{key}_seed{seed}.json"
            with (destination / path).open("x") as stream:
                json.dump(registry, stream, indent=2)
                stream.write("\n")
            e.setdefault("seed_configs", {})[str(seed)] = str(path)
        e["config"] = e["seed_configs"][str(e["seeds"][0])]
        if "kernel_equivalence_file" in e:
            copy_file(Path(e["kernel_equivalence_file"]))
    for name, value in (("manifest.json", {"source_code": source, "experiments": experiments}),):
        with (destination / name).open("x") as stream:
            json.dump(value, stream, indent=2)
            stream.write("\n")
    launcher = '''#!/bin/sh
set -eu
cd "$(dirname "$0")"
export PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export MPLCONFIGDIR="$PWD/.venv/matplotlib" TMPDIR="$PWD/.venv/runtime"
mkdir -p "$MPLCONFIGDIR" "$TMPDIR"
if [ ! -x .venv/science/bin/python ]; then
  "${RESEARCH_PYTHON:-python3.12}" -m venv .venv/science
  .venv/science/bin/python -m pip install -r requirements-research-macos-arm64-py312.txt
fi
exec .venv/science/bin/python -m src.chain.resume_transfer "$@"
'''
    with (destination / "resume.sh").open("x") as stream:
        stream.write(launcher)
    (destination / "resume.sh").chmod(0o755)
    receipts = {str(path.relative_to(destination)): file_sha256(path)
                for path in destination.rglob("*") if path.is_file()}
    with (destination / "SHA256SUMS.json").open("x") as stream:
        json.dump(receipts, stream, indent=2)
        stream.write("\n")
    return receipts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, nargs="+", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(f"Exported {len(export(args.manifest, args.output_dir))} checksummed files")


if __name__ == "__main__":
    main()
