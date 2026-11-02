"""State-configured entry point for the existing Gerrymander Detector tools.

This CLI orchestrates existing tools. It does not change the ReCom sampler,
validate complete legal compliance, or turn nonconverged ensembles into inference.
"""

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "configs" / "states.json"
ALIASES = {"tx": "texas", "nc": "north_carolina", "penn": "pennsylvania"}


class PipelineError(Exception):
    """A configuration or input preflight error."""


def load_registry(config_path=CONFIG_PATH):
    with Path(config_path).open(encoding="utf-8") as stream:
        registry = json.load(stream)
    if registry.get("schema_version") != 1:
        raise PipelineError("Unsupported state configuration schema version")
    states = registry.get("states")
    if not isinstance(states, dict):
        raise PipelineError("State configuration is missing 'states'")
    return states


def get_selection(states, state_key, year=None):
    try:
        state = states[state_key]
    except KeyError as exc:
        raise PipelineError(f"Unknown state: {state_key}") from exc

    if state.get("status") == "pending_data":
        if year is not None:
            raise PipelineError(f"{state['name']} has no validated plan years yet")
        return state, None, None

    plans = state.get("plans", {})
    plan_year = year or state.get("default_year")
    if plan_year not in plans:
        raise PipelineError(
            f"Unknown plan for {state['name']}: {plan_year!r}. "
            f"Available: {', '.join(plans)}"
        )
    plan = plans[plan_year]
    required = ("dataset", "layer", "districts", "columns")
    if any(key not in state for key in required):
        raise PipelineError(f"Missing required state configuration for {state_key}")
    if any(key not in state["columns"] for key in ("population", "dem", "rep")):
        raise PipelineError(f"Missing configured vote/population columns for {state_key}")
    if any(key not in plan for key in (
        "assignment", "state_label", "epsilon", "node_repeats",
        "output_dir", "checkpoint_dir", "audit"
    )):
        raise PipelineError(f"Missing plan configuration for {state_key}/{plan_year}")
    return state, plan_year, plan


def build_parser():
    parser = argparse.ArgumentParser(
        description="State-configured orchestration for validated redistricting inputs"
    )
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--texas", action="store_true", help="Texas")
    selection.add_argument("--nc", action="store_true", help="North Carolina")
    selection.add_argument("--penn", action="store_true", help="Pennsylvania (not yet prepared)")
    parser.add_argument("--year", help="Configured starting-plan year, e.g. 2023 or 2025")
    parser.add_argument("--config", type=Path, help="Explicit state registry inside this checkout")
    parser.add_argument(
        "--stage", choices=("status", "preflight", "validate", "rebuild", "simulate", "audit", "research-audit", "sources", "inventory", "download"), default="status",
        help="Status is read-only and does not execute simulation"
    )
    parser.add_argument("--steps", type=int, help="New states for simulate; total states for audit")
    parser.add_argument("--seed", type=int, help="Required for simulate")
    parser.add_argument("--seeds", nargs="+", type=int, help="Override audit seed list")
    parser.add_argument("--warmup", type=int, help="Override audit warmup")
    parser.add_argument("--window", type=int, help="Override audit window")
    parser.add_argument("--resume-from", type=Path, help="Checkpoint for simulate")
    parser.add_argument("--dry-run", action="store_true", help="Show the command; run nothing")
    parser.add_argument("--rdh-filter", help="Filter Pennsylvania RDH inventory listings")
    parser.add_argument("--rdh-file", help="Exact cached RDH filename to download")
    parser.add_argument("--report-dir", type=Path, help="New directory for preflight reports")
    parser.add_argument("--source-root", type=Path, help="Acquired RDH source directory for validate/rebuild")
    parser.add_argument("--block-master", type=Path, help="Audited block master CSV for rebuild")
    parser.add_argument("--rebuild-geography", choices=("block-union", "precinct"), help="NC rebuild geography; default: approved block-union baseline")
    parser.add_argument("--campaign-manifest", type=Path, help="Recorded experiment manifest for research-audit")
    return parser


def state_key_from_args(args):
    if args.texas:
        return "texas"
    if args.nc:
        return "north_carolina"
    return "pennsylvania"


def resolve(relative):
    path = Path(relative)
    return path if path.is_absolute() else ROOT / path


def epsilon_tag(epsilon):
    return f"{epsilon:g}".replace(".", "p")


def slug(label):
    return label.lower().replace(" ", "_")


def show_status(state, year, plan):
    print(f"STATE: {state['name']}")
    if plan is None:
        print("STATUS: PENDING DATA / NOT RESEARCH-VALIDATED")
        print(state["notes"])
        print("NEXT: authorize sources, build geography, and validate all inputs")
        return
    dataset = resolve(state["dataset"])
    print(f"STARTING PLAN: {year}")
    print(f"DATASET: {dataset}")
    print(f"DATASET EXISTS: {dataset.is_file()}")
    print(f"GEOGRAPHIC UNITS EXPECTED: {state.get('expected', {}).get('geographic_units', 'unknown')}")
    print(f"DISTRICTS: {state['districts']}")
    print(f"POPULATION TOLERANCE: +/-{plan['epsilon']:.3%}")
    print("RESEARCH STATUS: descriptive results; convergence not established")
    print(state.get("notes", ""))
    print("Use --stage simulate or --stage audit explicitly; no runs start by default.")


def build_simulation_command(args, state, plan):
    if args.seed is None or args.steps is None or args.steps <= 0:
        raise PipelineError("Simulate requires --seed INTEGER and --steps POSITIVE_INTEGER")
    if args.seeds or args.warmup is not None or args.window is not None:
        raise PipelineError("Audit-only flags cannot be used with simulate")

    start = 0
    if args.resume_from is not None:
        checkpoint = resolve(args.resume_from)
        pattern = (
            rf"^{re.escape(slug(plan['state_label']))}_checkpoint_"
            rf"eps{re.escape(epsilon_tag(plan['epsilon']))}_"
            rf"seed{args.seed}_next(\d+)\.pkl$"
        )
        match = re.fullmatch(pattern, checkpoint.name)
        if not match:
            raise PipelineError("Checkpoint filename does not match selected state, tolerance and seed")
        if not checkpoint.is_file() and not args.dry_run:
            raise PipelineError(f"Checkpoint missing: {checkpoint}")
        start = int(match.group(1))

    output_dir = resolve(plan["output_dir"])
    target = output_dir / (
        f"{slug(plan['state_label'])}_chain_eps{epsilon_tag(plan['epsilon'])}_"
        f"seed{args.seed}_steps{start:06d}-{start + args.steps - 1:06d}.csv"
    )
    if target.exists():
        raise PipelineError(f"Refusing to overwrite an existing chain segment: {target}")

    dataset = resolve(state["dataset"])
    if not dataset.is_file() and not args.dry_run:
        raise PipelineError(f"Validated dataset missing: {dataset}")

    columns = state["columns"]
    command = [
        sys.executable, str(ROOT / "src/chain/run_ensemble.py"),
        "--state", plan["state_label"],
        "--dataset", str(dataset),
        "--layer", state["layer"],
        "--assignment-col", plan["assignment"],
        "--population-col", columns["population"],
        "--dem-col", columns["dem"],
        "--rep-col", columns["rep"],
        "--steps", str(args.steps),
        "--epsilon", str(plan["epsilon"]),
        "--node-repeats", str(plan["node_repeats"]),
        "--seed", str(args.seed),
        "--output-dir", str(output_dir),
        "--checkpoint-dir", str(resolve(plan["checkpoint_dir"])),
    ]
    if args.resume_from is not None:
        command += ["--resume-from", str(resolve(args.resume_from))]
    return command, target


def build_audit_command(args, state, plan):
    if args.seed is not None or args.resume_from is not None:
        raise PipelineError("Simulation-only flags cannot be used with audit")
    audit = plan["audit"]
    steps = args.steps if args.steps is not None else audit["steps"]
    warmup = args.warmup if args.warmup is not None else audit["warmup"]
    window = args.window if args.window is not None else audit["window"]
    seeds = args.seeds if args.seeds is not None else audit["seeds"]
    if steps < 2 or not 0 <= warmup < steps or window < 1:
        raise PipelineError("Invalid audit steps, warmup or window")
    if len(seeds) < 2 or len(set(seeds)) != len(seeds):
        raise PipelineError("Audit requires at least two distinct seeds")
    from src.analysis.research_preflight import local_path
    destination = local_path(ROOT, args.report_dir or audit["output_dir"])
    if destination.exists():
        raise PipelineError("Refusing an existing audit output directory")

    command = [
        sys.executable, str(ROOT / "src/analysis/audit_ensemble_chains.py"),
        "--input-dir", str(resolve(plan["output_dir"])),
        "--prefix", audit["prefix"],
        "--seeds", *(str(seed) for seed in seeds),
        "--steps", str(steps),
        "--epsilon", str(plan["epsilon"]),
        "--districts", str(state["districts"]),
        "--warmup", str(warmup),
        "--window", str(window),
        "--output-dir", str(destination),
    ]
    if not resolve(plan["output_dir"]).is_dir() and not args.dry_run:
        raise PipelineError(f"Ensemble directory missing: {resolve(plan['output_dir'])}")
    return command


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        config_path = resolve(args.config).resolve() if args.config is not None else CONFIG_PATH
        config_path.relative_to(ROOT)
        states = load_registry(config_path)
        if args.report_dir is not None and args.stage not in ("preflight", "validate", "rebuild", "audit", "research-audit"):
            raise PipelineError("--report-dir requires a report-producing stage")
        if args.campaign_manifest is not None and args.stage != "research-audit":
            raise PipelineError("--campaign-manifest requires --stage research-audit")
        if args.rebuild_geography is not None and (args.stage != "rebuild" or not args.nc):
            raise PipelineError("--rebuild-geography requires --nc --stage rebuild")
        if args.source_root is not None and args.stage not in ("validate", "rebuild"):
            raise PipelineError("--source-root requires --stage validate or rebuild")
        if args.block_master is not None and args.stage != "rebuild":
            raise PipelineError("--block-master requires --stage rebuild")
        if args.stage in ("sources", "inventory", "download"):
            if not args.penn:
                raise PipelineError("RDH source stages currently support Pennsylvania only")
            if any(v is not None for v in (
                args.year, args.steps, args.seed, args.seeds,
                args.warmup, args.window, args.resume_from
            )):
                raise PipelineError("Simulation and audit options cannot be used with RDH stages")
            from src.data.rdh_client import run_pennsylvania
            return run_pennsylvania(
                args.stage, query=args.rdh_filter,
                filename=args.rdh_file, dry_run=args.dry_run
            )
        if args.rdh_filter is not None or args.rdh_file is not None:
            raise PipelineError("RDH options require --stage sources, inventory or download")
        state, year, plan = get_selection(states, state_key_from_args(args), args.year)
        if args.stage == "status":
            if any(v is not None for v in (args.steps, args.seed, args.seeds, args.warmup, args.window, args.resume_from)):
                raise PipelineError("Run options require --stage simulate or --stage audit")
            show_status(state, year, plan)
            return 0

        if plan is None:
            raise PipelineError(
                f"{state['name']} has no validated dataset or plan configuration. "
                "Data ingestion and validation must be completed before running this stage."
            )
        if args.stage == "research-audit":
            if args.campaign_manifest is None or args.report_dir is None:
                raise PipelineError("Research-audit requires --campaign-manifest and --report-dir")
            if any(v is not None for v in (args.year, args.steps, args.seed, args.seeds, args.warmup, args.window, args.resume_from)):
                raise PipelineError("Research-audit uses every configured state experiment without run overrides")
            from src.analysis.research_preflight import local_path
            manifest_path = local_path(ROOT, args.campaign_manifest)
            destination = local_path(ROOT, args.report_dir)
            if destination.exists():
                raise PipelineError("Refusing an existing research audit output directory")
            manifest = json.loads(manifest_path.read_text())
            if not isinstance(manifest.get("experiments"), dict):
                raise PipelineError("Campaign manifest requires an experiments object")
            experiments = [key for key, value in manifest["experiments"].items()
                           if value["state"] == state_key_from_args(args)]
            if not experiments:
                raise PipelineError("No experiments for the selected state in this manifest")
            command = [sys.executable, str(ROOT / "src/analysis/audit_rebuild_campaign.py"),
                       "--manifest", str(manifest_path), "--output-dir", str(destination),
                       "--experiments", *experiments]
            print("COMMAND: " + subprocess.list2cmdline(command))
            if args.dry_run:
                print("DRY RUN: no files written, no subprocess started")
                return 0
            env = os.environ.copy()
            env.setdefault("MPLCONFIGDIR", str(ROOT / ".venv/matplotlib"))
            return subprocess.run(command, cwd=ROOT, env=env, check=False).returncode
        if args.stage in ("validate", "rebuild"):
            if any(v is not None for v in (
                args.steps, args.seed, args.seeds, args.warmup, args.window, args.resume_from
            )):
                raise PipelineError("Run overrides cannot be used with validate/rebuild")
            if args.source_root is None or args.report_dir is None:
                raise PipelineError("Validate/rebuild requires --source-root and --report-dir")
            from src.analysis.research_preflight import local_path
            source = local_path(ROOT, args.source_root)
            destination = local_path(ROOT, args.report_dir)
            if destination.exists():
                raise PipelineError("Refusing an existing validation/rebuild output directory")
            state_key = state_key_from_args(args)
            if args.stage == "validate":
                commands = [[
                    sys.executable, str(ROOT / script), "--state", state_key,
                    "--source-root", str(source), "--output-dir", str(destination / folder),
                ] for script, folder in (
                    ("src/validation/audit_rdh_sources.py", "blocks"),
                    ("src/validation/audit_rdh_geometry.py", "geometry"),
                )]
            else:
                if args.block_master is None:
                    raise PipelineError("Rebuild requires --block-master from a successful source audit")
                master = local_path(ROOT, args.block_master)
                script = "rebuild_texas_candidate.py" if args.texas else (
                    "rebuild_nc_common.py" if args.rebuild_geography == "precinct" else "rebuild_nc_block_union.py")
                commands = [[
                    sys.executable, str(ROOT / "src/data_prep" / script),
                    "--source-root", str(source), "--block-master", str(master),
                    "--output-dir", str(destination),
                ]]
            for command in commands:
                print("COMMAND: " + subprocess.list2cmdline(command), flush=True)
            if args.dry_run:
                print("DRY RUN: no files written, no subprocess started")
                return 0
            failures = [subprocess.run(command, cwd=ROOT, check=False).returncode
                        for command in commands]
            print("RESEARCH-READY: NO; source audits/candidates do not establish scientific readiness")
            return max((abs(code) for code in failures), default=0)
        if args.stage == "preflight":
            if any(v is not None for v in (
                args.steps, args.seed, args.seeds, args.warmup, args.window, args.resume_from
            )):
                raise PipelineError("Preflight inventories configured runs; run options are not supported")
            from src.analysis.research_preflight import build_report, local_path, write_report
            destination = local_path(ROOT, args.report_dir) if args.report_dir is not None else None
            if args.dry_run:
                print(f"DRY RUN: preflight report target: {destination or 'stdout'}")
                return 0
            report = build_report(
                ROOT, state_key_from_args(args), year, state, plan,
                [sys.executable, str(ROOT / "main.py"), *(argv if argv is not None else sys.argv[1:])],
            )
            if destination is not None:
                write_report(report, destination)
                print(f"REPORT: {destination}")
                print("EXECUTION: completed; RESEARCH-READY: NO")
            else:
                print(json.dumps(report, indent=2, allow_nan=False))
            return 0
        if args.stage == "simulate":
            command, target = build_simulation_command(args, state, plan)
            print(f"TARGET (will not overwrite): {target}")
        else:
            command = build_audit_command(args, state, plan)
        print("COMMAND: " + subprocess.list2cmdline(command))
        if args.dry_run:
            print("DRY RUN: no files written, no subprocess started")
            return 0
        env = os.environ.copy()
        env.setdefault("PYTHONHASHSEED", "0")
        env.setdefault("MPLCONFIGDIR", str(ROOT / ".venv/matplotlib"))
        return subprocess.run(command, cwd=ROOT, env=env, check=False).returncode
    except (PipelineError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
