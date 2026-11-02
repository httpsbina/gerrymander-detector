"""Compare RDH modeled presidential allocations with unsorted official NC returns.

Only county aggregates are compared. Privacy noise is never inverted or removed.
"""

import argparse
from collections import defaultdict
import csv
import io
import json
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--official-zip", type=Path, required=True)
    parser.add_argument("--block-master", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    for path in (args.official_zip, args.block_master, args.output):
        path.resolve().relative_to(ROOT)
    if args.output.exists():
        raise FileExistsError("Refusing existing county comparison")
    official, modeled = defaultdict(lambda: [0, 0]), defaultdict(lambda: [0, 0])
    choices = set()
    identities = set()
    with ZipFile(args.official_zip) as archive, archive.open("results_pct_20241105.txt") as raw:
        reader = csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig", newline=""), delimiter="\t")
        for row in reader:
            if row["Contest Name"] != "US PRESIDENT" or row["Choice Party"] not in ("DEM", "REP"):
                continue
            identity = (row["County"], row["Precinct"], row["Choice"])
            if identity in identities:
                raise ValueError("Duplicate official county/precinct/candidate row")
            identities.add(identity)
            values = [int(row[name]) for name in ("Election Day", "Early Voting", "Absentee by Mail", "Provisional")]
            total = int(row["Total Votes"])
            if min(values) < 0 or sum(values) != total:
                raise ValueError("Official voting-method totals are inconsistent")
            party = 0 if row["Choice Party"] == "DEM" else 1
            official[row["County"].strip().upper()][party] += total
            choices.add((row["Choice Party"], row["Choice"]))
    with args.block_master.open(newline="") as stream:
        for row in csv.DictReader(stream):
            county = row["PRECINCTID"].split("-:-")[0].strip().upper()
            modeled[county][0] += int(row["G24PREDHAR"])
            modeled[county][1] += int(row["G24PRERTRU"])
    if set(official) != set(modeled) or len(official) != 100 or len(choices) != 2:
        raise ValueError("County or candidate coverage mismatch")
    counties = []
    for county in sorted(official):
        diff = [official[county][i] - modeled[county][i] for i in (0, 1)]
        counties.append({"county": county, "official_dem": official[county][0], "official_rep": official[county][1],
                         "rdh_modeled_dem": modeled[county][0], "rdh_modeled_rep": modeled[county][1],
                         "official_minus_rdh_dem": diff[0], "official_minus_rdh_rep": diff[1]})
    report = {"research_ready": False, "official_candidates": sorted(choices),
              "official_rows": len(identities), "counties": counties,
              "official_totals": {"dem": sum(v[0] for v in official.values()), "rep": sum(v[1] for v in official.values())},
              "rdh_modeled_totals": {"dem": sum(v[0] for v in modeled.values()), "rep": sum(v[1] for v in modeled.values())},
              "counties_with_any_difference": sum(any(row[key] for key in ("official_minus_rdh_dem", "official_minus_rdh_rep")) for row in counties),
              "sum_absolute_county_differences": {party: sum(abs(row[f"official_minus_rdh_{party}"]) for row in counties) for party in ("dem", "rep")},
              "interpretation": "RDH documents mixed sorted/unsorted sources and privacy noise. Differences are measured, not all causally attributed to noise. No modeled vote is corrected or redistributed."}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({key:value for key,value in report.items() if key != "counties"}, indent=2))


if __name__ == "__main__":
    main()
