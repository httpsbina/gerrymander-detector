"""Descriptive election-choice and uniform-swing sensitivity on official blocks."""

import argparse
import csv
import io
import json
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[2]
MODELS = {
    "texas": {
        "president_2024": ("G24PREDHAR", "G24PRERTRU"),
        "us_senate_2024": ("G24USSDALL", "G24USSRCRU"),
    },
    "north_carolina": {
        "president_2024": ("G24PREDHAR", "G24PRERTRU"),
        "governor_2024": ("G24GOVDSTE", "G24GOVRROB"),
        "attorney_general_2024": ("G24ATGDJAC", "G24ATGRBIS"),
    },
}


def swing_seats(district_votes, shift):
    if any(dem + rep <= 0 for dem, rep in district_votes):
        raise ValueError("Undefined two-party share in an empty-vote district")
    return sum(min(1.0, max(0.0, dem / (dem + rep) + shift)) > 0.5
               for dem, rep in district_votes)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", choices=MODELS, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--block-master", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    for path in (args.source_root, args.block_master, args.output):
        path.resolve().relative_to(ROOT)
    if args.output.exists():
        raise FileExistsError("Refusing existing election sensitivity report")
    prefix, years, districts = ("tx", (2025,), 38) if args.state == "texas" else ("nc", (2023, 2025), 14)
    with args.block_master.open(newline="") as stream:
        reader = csv.DictReader(stream)
        assignments = {}
        for row in reader:
            geoid = row["GEOID20"]
            if geoid in assignments:
                raise ValueError("Duplicate master block")
            assignments[geoid] = {year: int(row[f"DISTRICT_{year}"]) for year in years}
    counts = {model: {year: {district: [0, 0] for district in range(1, districts + 1)}
                      for year in years} for model in MODELS[args.state]}
    source = args.source_root / args.state / f"{prefix}_2024_gen_2020_blocks_csv.zip"
    seen = set()
    with ZipFile(source) as archive, archive.open(f"{prefix}_2024_gen_2020_blocks.csv") as raw:
        reader = csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig", newline=""))
        required = {column for pair in MODELS[args.state].values() for column in pair} | {"GEOID20"}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError("Missing election sensitivity fields")
        for row in reader:
            geoid = row["GEOID20"]
            if geoid in seen or geoid not in assignments:
                raise ValueError("Duplicate or unmatched election block")
            seen.add(geoid)
            for model, columns in MODELS[args.state].items():
                dem, rep = (int(row[column]) for column in columns)
                if min(dem, rep) < 0:
                    raise ValueError("Negative model votes")
                for year in years:
                    values = counts[model][year][assignments[geoid][year]]
                    values[0] += dem
                    values[1] += rep
    if seen != set(assignments):
        raise ValueError("Election models do not cover every master block")
    report = {"state": args.state, "research_ready": False, "blocks": len(seen), "models": {},
              "interpretation": "Descriptive modeled block scores; election choice and uniform swing are sensitivity scenarios, not calibrated probabilities or observed block votes"}
    president = counts["president_2024"][years[0]].values()
    president_dem = sum(row[0] for row in president)
    president_total = sum(sum(row) for row in counts["president_2024"][years[0]].values())
    target_share = president_dem / president_total
    for model, by_year in counts.items():
        result = {}
        for year, by_district in by_year.items():
            values = list(by_district.values())
            dem_total, rep_total = sum(row[0] for row in values), sum(row[1] for row in values)
            model_share = dem_total / (dem_total + rep_total)
            normalizing_shift = target_share - model_share
            result[str(year)] = {
                "dem_modeled_votes": dem_total, "rep_modeled_votes": rep_total,
                "statewide_dem_two_party_share": dem_total / (dem_total + rep_total),
                "dem_modeled_seats": swing_seats(values, 0),
                "minimum_absolute_two_party_vote_margin": min(abs(dem - rep) for dem, rep in values),
                "uniform_swing_dem_seats": {f"{shift:+.2f}": swing_seats(values, shift)
                                            for shift in (-0.03, -0.02, -0.01, 0, 0.01, 0.02, 0.03)},
                "normalized_to_presidential_statewide_share": {
                    "target_dem_two_party_share": target_share,
                    "uniform_district_share_shift": normalizing_shift,
                    "dem_modeled_seats": swing_seats(values, normalizing_shift),
                    "interpretation": "Uniform-swing scenario controlling gross statewide candidate support; not a correction to observed data",
                },
            }
        report["models"][model] = result
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
