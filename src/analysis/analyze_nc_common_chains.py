"""Validate and diagnose the six NC common-geography ReCom chains."""

import re
from pathlib import Path

import arviz as az
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
ENSEMBLES = ROOT / "outputs/ensembles"
OUTPUT = ROOT / "outputs/analysis"
YEARS = (2023, 2025)
SEEDS = (707, 808, 909)
METRICS = ("dem_seats", "efficiency_gap", "cut_edges")
STEPS = 5000
WARMUP = 500
EPSILON = 0.005


def load_runs():
    runs = {}
    required = {
        "step", "seed", "epsilon", "dem_seats",
        "efficiency_gap", "cut_edges",
        "max_abs_pop_dev", "plan_hash"
    }

    for year in YEARS:
        for seed in SEEDS:
            pattern = (
                f"north_carolina_common_{year}_chain_"
                f"eps0p005_seed{seed}_steps*.csv"
            )
            files = sorted(ENSEMBLES.glob(pattern))

            if not files:
                raise FileNotFoundError(pattern)

            parts = []

            for path in files:
                match = re.search(
                    r"steps(\d+)-(\d+)\.csv$", path.name
                )
                if not match:
                    raise ValueError(f"Invalid file name: {path}")

                start, end = map(int, match.groups())
                df = pd.read_csv(path)

                if not required.issubset(df.columns):
                    raise ValueError(f"Missing columns: {path}")

                if df[list(required)].isna().any().any():
                    raise ValueError(f"Missing values: {path}")

                if df.step.tolist() != list(range(start, end + 1)):
                    raise ValueError(f"Incorrect steps: {path}")

                if not (df.seed == seed).all():
                    raise ValueError(f"Incorrect seed: {path}")

                if not np.allclose(
                    df.epsilon, EPSILON, atol=1e-10
                ):
                    raise ValueError(f"Incorrect epsilon: {path}")

                if (
                    df.max_abs_pop_dev > EPSILON + 1e-10
                ).any():
                    raise ValueError(f"Population violation: {path}")

                if not df.dem_seats.between(0, 14).all():
                    raise ValueError(f"Invalid seats: {path}")

                if not df.plan_hash.astype(str).str.fullmatch(
                    r"[a-f0-9]{64}"
                ).all():
                    raise ValueError(f"Invalid plan hash: {path}")

                parts.append(df)

            run = pd.concat(parts, ignore_index=True)
            run = run.sort_values("step").reset_index(drop=True)

            if run.step.tolist() != list(range(STEPS)):
                raise ValueError(
                    f"Incomplete/overlapping run: {year}, {seed}"
                )

            if int(run.dem_seats.iloc[0]) != 3:
                raise ValueError(
                    f"Unexpected initial seats: {year}, {seed}"
                )

            runs[year, seed] = run

    return runs


def diagnostics(samples):
    rhat = float(np.asarray(
        az.rhat(samples, method="rank")
    ).item())

    bulk = float(np.asarray(
        az.ess(samples, method="bulk")
    ).item())

    tail = float(np.asarray(
        az.ess(
            samples,
            method="tail",
            prob=(0.05, 0.95)
        )
    ).item())

    return rhat, bulk, tail


def main():
    runs = load_runs()
    summaries, windows, results = [], [], []

    for (year, seed), run in runs.items():
        kept = run.iloc[WARMUP:]

        summaries.append({
            "starting_map": year,
            "seed": seed,
            "total_states": len(run),
            "retained_states": len(kept),
            "unique_plans": run.plan_hash.nunique(),
            "mean_seats": kept.dem_seats.mean(),
            "seats_le_3": int((kept.dem_seats <= 3).sum()),
            "mean_efficiency_gap": kept.efficiency_gap.mean(),
            "plan_change_rate": (
                run.plan_hash.iloc[1:].to_numpy()
                != run.plan_hash.iloc[:-1].to_numpy()
            ).mean(),
            "seat_change_rate": (
                run.dem_seats.iloc[1:].to_numpy()
                != run.dem_seats.iloc[:-1].to_numpy()
            ).mean(),
        })

        for first in range(0, STEPS, 1000):
            w = run.iloc[first:first + 1000]

            windows.append({
                "starting_map": year,
                "seed": seed,
                "window_start": first,
                "window_end": first + 999,
                "mean_seats": w.dem_seats.mean(),
                "mean_efficiency_gap": w.efficiency_gap.mean(),
                "seats_le_3": int((w.dem_seats <= 3).sum()),
            })

    groups = [
        (str(year), [(year, seed) for seed in SEEDS])
        for year in YEARS
    ]
    groups.append(("all_six", list(runs)))

    for name, keys in groups:
        for metric in METRICS:
            samples = np.stack([
                runs[key].iloc[WARMUP:][metric].to_numpy(float)
                for key in keys
            ])

            rhat, bulk, tail = diagnostics(samples)

            results.append({
                "group": name,
                "metric": metric,
                "retained_states": samples.size,
                "rank_rhat": rhat,
                "bulk_ess": bulk,
                "tail_ess": tail,
            })

    OUTPUT.mkdir(parents=True, exist_ok=True)

    summary = pd.DataFrame(summaries)
    windows_df = pd.DataFrame(windows)
    convergence = pd.DataFrame(results)

    summary.to_csv(
        OUTPUT / "nc_common_chain_summary.csv", index=False
    )
    windows_df.to_csv(
        OUTPUT / "nc_common_window_summary.csv", index=False
    )
    convergence.to_csv(
        OUTPUT / "nc_common_convergence.csv", index=False
    )

    print("NC COMMON-GEOGRAPHY CHAIN SUMMARY")
    print(summary.round(4).to_string(index=False))

    print("\nCONVERGENCE (FIRST 500 STATES DISCARDED)")
    print(convergence.round(4).to_string(index=False))

    print(
        "\nConvergence is not established; "
        "rare outcome counts are descriptive."
    )
    print(f"Saved three CSV tables to {OUTPUT}")


if __name__ == "__main__":
    main()
