"""Validate segmented ReCom chains and report mixing diagnostics."""

import argparse
import re
from itertools import groupby
from pathlib import Path

import arviz as az
import numpy as np
import pandas as pd

METRICS = ("dem_seats", "efficiency_gap", "cut_edges")
REQUIRED = {
    "step", "seed", "epsilon", "dem_seats",
    "efficiency_gap", "cut_edges",
    "max_abs_pop_dev", "plan_hash",
}


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--prefix", required=True)
    parser.add_argument("--seeds", type=int, nargs="+", required=True)
    parser.add_argument("--steps", type=int, required=True)
    parser.add_argument("--epsilon", type=float, required=True)
    parser.add_argument("--districts", type=int, required=True)
    parser.add_argument("--warmup", type=int, default=0)
    parser.add_argument("--window", type=int, default=1000)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def load_chain(args, seed):
    tag = f"{args.epsilon:g}".replace(".", "p")
    pattern = (
        f"{args.prefix}_chain_eps{tag}_"
        f"seed{seed}_steps*.csv"
    )
    files = sorted(args.input_dir.glob(pattern))

    if not files:
        raise FileNotFoundError(
            f"No files matched {args.input_dir / pattern}"
        )

    chunks = []

    for file in files:
        match = re.search(
            r"steps(\d+)-(\d+)\.csv$", file.name
        )

        if not match:
            raise ValueError(f"Unexpected filename: {file}")

        first, last = map(int, match.groups())
        frame = pd.read_csv(file)

        if not REQUIRED.issubset(frame.columns):
            raise ValueError(f"Missing columns: {file}")

        if frame[list(REQUIRED)].isna().any().any():
            raise ValueError(f"Missing values: {file}")

        if frame.step.tolist() != list(
            range(first, last + 1)
        ):
            raise ValueError(f"Invalid step segment: {file}")

        if not (frame.seed == seed).all():
            raise ValueError(f"Seed mismatch: {file}")

        if not np.allclose(
            frame.epsilon, args.epsilon,
            rtol=0, atol=1e-10
        ):
            raise ValueError(f"Epsilon mismatch: {file}")

        if (
            (frame.max_abs_pop_dev < 0).any()
            or (
                frame.max_abs_pop_dev
                > args.epsilon + 1e-10
            ).any()
        ):
            raise ValueError(
                f"Population tolerance violation: {file}"
            )

        if not frame.dem_seats.between(
            0, args.districts
        ).all():
            raise ValueError(f"Invalid seats: {file}")

        if not frame.plan_hash.astype(
            str
        ).str.fullmatch(r"[a-f0-9]{64}").all():
            raise ValueError(f"Invalid plan hashes: {file}")

        chunks.append(frame)

    run = pd.concat(
        chunks, ignore_index=True
    ).sort_values("step").reset_index(drop=True)

    if run.step.tolist() != list(range(args.steps)):
        raise ValueError(
            f"Missing or duplicate steps for seed {seed}"
        )

    return run


def scalar(value):
    return float(np.asarray(value).item())


def main():
    args = parse_args()

    if len(set(args.seeds)) != len(args.seeds):
        raise ValueError("Seeds must be distinct")

    if args.steps < 2 or not (
        0 <= args.warmup < args.steps
    ):
        raise ValueError("Invalid steps or warmup")

    if (
        args.epsilon <= 0
        or args.districts < 1
        or args.window < 1
    ):
        raise ValueError("Invalid analysis parameters")

    chains = {
        seed: load_chain(args, seed)
        for seed in args.seeds
    }

    initial_hashes = {
        df.plan_hash.iloc[0]
        for df in chains.values()
    }

    if len(initial_hashes) != 1:
        raise ValueError(
            "Different starting maps within experiment"
        )

    summaries = []
    windows = []
    convergence = []

    for seed, run in chains.items():
        post = run.iloc[args.warmup:]

        hashes = run.plan_hash.to_numpy()
        seats = run.dem_seats.to_numpy()

        plan_changes = (
            hashes[1:] != hashes[:-1]
        ).mean()

        seat_changes = (
            seats[1:] != seats[:-1]
        ).mean()

        longest_run = max(
            sum(1 for _ in group)
            for _, group in groupby(seats)
        )

        summaries.append({
            "seed": seed,
            "states": len(run),
            "retained_states": len(post),
            "unique_plans": run.plan_hash.nunique(),
            "mean_dem_seats": post.dem_seats.mean(),
            "min_dem_seats": post.dem_seats.min(),
            "max_dem_seats": post.dem_seats.max(),
            "mean_efficiency_gap": (
                post.efficiency_gap.mean()
            ),
            "max_pop_deviation": (
                run.max_abs_pop_dev.max()
            ),
            "plan_change_rate": plan_changes,
            "seat_change_rate": seat_changes,
            "longest_identical_seat_run": longest_run,
        })

        for start in range(
            0, len(run), args.window
        ):
            part = run.iloc[
                start:start + args.window
            ]

            windows.append({
                "seed": seed,
                "first_step": int(part.step.iloc[0]),
                "last_step": int(part.step.iloc[-1]),
                "mean_dem_seats": (
                    part.dem_seats.mean()
                ),
                "mean_efficiency_gap": (
                    part.efficiency_gap.mean()
                ),
            })

    retained = args.steps - args.warmup

    if len(chains) >= 2 and retained >= 1000:
        for metric in METRICS:
            samples = np.stack([
                chains[seed]
                .iloc[args.warmup:][metric]
                .to_numpy(float)
                for seed in args.seeds
            ])

            convergence.append({
                "metric": metric,
                "rank_rhat": scalar(
                    az.rhat(
                        samples, method="rank"
                    )
                ),
                "bulk_ess": scalar(
                    az.ess(
                        samples, method="bulk"
                    )
                ),
                "tail_ess": scalar(
                    az.ess(
                        samples, method="tail", prob=(0.05, 0.95)
                    )
                ),
            })

    args.output_dir.mkdir(
        parents=True, exist_ok=True
    )

    pd.DataFrame(summaries).to_csv(
        args.output_dir / "chain_summary.csv",
        index=False
    )

    pd.DataFrame(windows).to_csv(
        args.output_dir / "window_summary.csv",
        index=False
    )

    print("\nCHAIN INTEGRITY: PASS")
    print("=" * 65)
    print(
        pd.DataFrame(summaries)
        .round(4)
        .to_string(index=False)
    )

    if convergence:
        pd.DataFrame(convergence).to_csv(
            args.output_dir / "convergence.csv",
            index=False
        )

        print("\nPROVISIONAL MIXING DIAGNOSTICS")
        print("=" * 65)
        print(
            pd.DataFrame(convergence)
            .round(4)
            .to_string(index=False)
        )
        print(
            "\nThese diagnostics do not "
            "establish convergence."
        )
    else:
        print(
            "\nConvergence diagnostics skipped: "
            "requires at least two chains and "
            "1,000 retained states per chain."
        )

    print(
        f"\nSaved audit tables: {args.output_dir}"
    )


if __name__ == "__main__":
    main()

