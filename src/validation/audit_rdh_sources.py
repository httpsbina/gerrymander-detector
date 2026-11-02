"""Audit freshly acquired RDH block sources without changing their contents.

Scores use modeled block allocations, not observed block election returns.
No simulation, geometry repair, or inference is performed here.
"""

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import struct
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[2]
STATES = {
    "texas": ("tx", "48", 668757, (2025,), 38),
    "north_carolina": ("nc", "37", 236638, (2023, 2025), 14),
}


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_geoid(geoid, fips):
    if len(geoid) != 15 or not geoid.isascii() or not geoid.isdigit() or not geoid.startswith(fips):
        raise ValueError(f"Invalid block identifier: {geoid!r}")


def read_population(path, member, fips):
    population = {}
    with ZipFile(path) as archive, archive.open(member) as stream:
        header = stream.read(32)
        count, header_size, record_size = struct.unpack("<IHH", header[4:12])
        fields, offset = {}, 1
        for _ in range((header_size - 33) // 32):
            descriptor = stream.read(32)
            name = descriptor[:11].split(b"\0")[0].decode("ascii")
            width = descriptor[16]
            fields[name] = (offset, width)
            offset += width
        if stream.read(1) != b"\r" or offset != record_size:
            raise ValueError("Invalid DBF record layout")
        if not {"GEOID20", "P0010001"}.issubset(fields):
            raise ValueError("Missing Census block population fields")
        for _ in range(count):
            record = stream.read(record_size)
            if len(record) != record_size or record[:1] != b" ":
                raise ValueError("Truncated or deleted Census record")
            values = {}
            for name in ("GEOID20", "P0010001"):
                start, width = fields[name]
                values[name] = record[start:start + width].decode("ascii").strip()
            geoid, pop = values["GEOID20"], int(values["P0010001"])
            validate_geoid(geoid, fips)
            if geoid in population or pop < 0:
                raise ValueError("Duplicate block or negative Census population")
            population[geoid] = pop
    return population


def read_votes(path, member, fips):
    votes, precincts = {}, set()
    with ZipFile(path) as archive, archive.open(member) as raw:
        reader = csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig", newline=""))
        required = {"GEOID20", "PRECINCTID", "G24PREDHAR", "G24PRERTRU"}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError("Missing block election fields")
        for row in reader:
            geoid = row["GEOID20"].strip()
            validate_geoid(geoid, fips)
            precinct = row["PRECINCTID"].strip()
            dem, rep = int(row["G24PREDHAR"]), int(row["G24PRERTRU"])
            if geoid in votes or not precinct or min(dem, rep) < 0:
                raise ValueError("Duplicate block, missing precinct, or negative block votes")
            votes[geoid] = (precinct, dem, rep)
            precincts.add(precinct)
    return votes, precincts


def read_plan(path, fips, districts):
    assignments = {}
    with ZipFile(path) as archive:
        members = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if len(members) != 1:
            raise ValueError("Expected exactly one official block assignment CSV")
        with archive.open(members[0]) as raw:
            reader = csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig", newline=""))
            geoid_col = "SCTBKEY" if "SCTBKEY" in (reader.fieldnames or []) else "Block"
            district_col = "DISTRICT" if "DISTRICT" in (reader.fieldnames or []) else "District"
            if not {geoid_col, district_col}.issubset(reader.fieldnames or []):
                raise ValueError("Missing official plan assignment fields")
            for row in reader:
                geoid, district = row[geoid_col].strip(), int(row[district_col])
                validate_geoid(geoid, fips)
                if geoid in assignments or district not in range(1, districts + 1):
                    raise ValueError("Duplicate block or invalid district assignment")
                assignments[geoid] = district
    if set(assignments.values()) != set(range(1, districts + 1)):
        raise ValueError("Missing district labels in official assignment")
    return assignments


def audit(state, source_root, destination):
    prefix, fips, expected_blocks, years, districts = STATES[state]
    with (ROOT / "configs/states.json").open() as stream:
        expected = json.load(stream)["states"][state]["expected"]
    source = source_root / state
    population_path = source / f"{prefix}_pl2020_b.zip"
    election_path = source / f"{prefix}_2024_gen_2020_blocks_csv.zip"
    population = read_population(population_path, f"{prefix}_pl2020_p1_b.dbf", fips)
    votes, precincts = read_votes(election_path, f"{prefix}_2024_gen_2020_blocks.csv", fips)
    population_ids, vote_ids = set(population), set(votes)
    errors = []
    if population_ids != vote_ids:
        errors.append("Population and election block sets differ")
    if len(population) != expected_blocks:
        errors.append("Census block count differs from historical expectation")
    totals = {"population": sum(population.values()),
              "dem_votes": sum(value[1] for value in votes.values()),
              "rep_votes": sum(value[2] for value in votes.values())}
    for name, value in totals.items():
        if value != expected[name]:
            errors.append(f"{name} differs from historical configured total")
    report = {
        "state": state, "research_ready": False,
        "attribution": "This analysis was conducted using data from the Redistricting Data Hub.",
        "vote_interpretation": "Modeled allocations to Census blocks, not observed block returns",
        "population_blocks": len(population), "election_blocks": len(votes),
        "election_precinct_ids": len(precincts), "zero_population_blocks": sum(v == 0 for v in population.values()),
        "population_blocks_missing_votes": len(population_ids - vote_ids),
        "vote_blocks_missing_population": len(vote_ids - population_ids),
        "totals": totals, "historical_expected_totals": expected,
        "source_files": [], "plans": {}, "errors": errors,
        "geometry_validation": "not run", "convergence_diagnostics": "unavailable; no chains",
    }
    paths = [population_path, election_path]
    plans = {}
    for year in years:
        path = source / f"{prefix}_cong_adopted_{year}.zip"
        paths.append(path)
        assignments = read_plan(path, fips, districts)
        plans[year] = assignments
        ids = set(assignments)
        coverage = ids == population_ids == vote_ids
        summary = {"assignment_blocks": len(assignments), "exact_block_set_match": coverage,
                   "missing_population_blocks": len(population_ids - ids),
                   "extra_assignment_blocks": len(ids - population_ids)}
        if not coverage:
            errors.append(f"{year} plan block coverage mismatch")
        else:
            counts = {district: [0, 0, 0, 0] for district in range(1, districts + 1)}
            for geoid, district in assignments.items():
                row = counts[district]
                row[0] += 1
                row[1] += population[geoid]
                row[2] += votes[geoid][1]
                row[3] += votes[geoid][2]
            ideal = totals["population"] / districts
            summary["districts"] = [
                {"district": district, "blocks": row[0], "population": row[1],
                 "dem_modeled_votes": row[2], "rep_modeled_votes": row[3],
                 "dem_two_party_share": row[2] / (row[2] + row[3]) if row[2] + row[3] else None,
                 "population_relative_deviation": row[1] / ideal - 1}
                for district, row in sorted(counts.items())
            ]
            summary["dem_modeled_seats"] = sum(row[2] > row[3] for row in counts.values())
            summary["tied_districts"] = sum(row[2] == row[3] for row in counts.values())
            summary["max_abs_population_deviation"] = max(abs(row[1] / ideal - 1) for row in counts.values())
        report["plans"][str(year)] = summary
    if len(plans) == 2 and set(plans[2023]) == set(plans[2025]) == population_ids == vote_ids:
        changed = [geoid for geoid in population if plans[2023][geoid] != plans[2025][geoid]]
        report["assignment_changes"] = {
            "blocks": len(changed), "population": sum(population[g] for g in changed),
            "dem_modeled_votes": sum(votes[g][1] for g in changed),
            "rep_modeled_votes": sum(votes[g][2] for g in changed),
        }
        onslow = [g for g in population if votes[g][0] == "ONSLOW-:-SW19"]
        report["onslow_sw19"] = {
            "blocks": len(onslow), "population": sum(population[g] for g in onslow),
            "assignment_pairs": sorted({(plans[2023][g], plans[2025][g]) for g in onslow}),
            "geometry_verified": False,
        }
    for path in paths:
        report["source_files"].append({"path": str(path), "bytes": path.stat().st_size,
                                       "sha256": sha256(path)})
    report["tabular_integrity"] = "fail" if errors else "pass"
    destination.mkdir(parents=True, exist_ok=False)
    with (destination / "source_audit.json").open("x") as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write("\n")
    if not errors:
        with (destination / "blocks_master.csv").open("x", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(["GEOID20", "PRECINCTID", "TOTPOP", "G24PREDHAR", "G24PRERTRU",
                             *(f"DISTRICT_{year}" for year in years)])
            for geoid in sorted(population):
                precinct, dem, rep = votes[geoid]
                writer.writerow([geoid, precinct, population[geoid], dem, rep,
                                 *(plans[year][geoid] for year in years)])
    print(json.dumps({key: report[key] for key in (
        "state", "tabular_integrity", "population_blocks", "election_blocks", "totals", "errors"
    )}, indent=2))
    return 1 if errors else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", choices=STATES, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    for path in (args.source_root, args.output_dir):
        path.resolve().relative_to(ROOT)
    return audit(args.state, args.source_root, args.output_dir)


if __name__ == "__main__":
    raise SystemExit(main())
