"""Join North Carolina Census population and 2024 presidential votes."""

import csv
import io
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[2]
POP_PATH = ROOT / "data/processed/nc_blocks_population.csv"
ELECTION_ZIP = ROOT / "data/raw/nc/nc_2024_gen_2020_blocks_csv.zip"
OUTPUT = ROOT / "data/processed/nc_blocks_election.csv"

EXPECTED_BLOCKS = 236_638
EXPECTED_POPULATION = 10_439_388
EXPECTED_HARRIS = 2_713_609
EXPECTED_TRUMP = 2_896_942

print("Loading validated NC Census population...")

population = {}

with POP_PATH.open(newline="", encoding="utf-8-sig") as file:
    reader = csv.DictReader(file)

    if not {"GEOID20", "TOTPOP"} <= set(reader.fieldnames or []):
        raise ValueError("Missing population columns")

    for row in reader:
        geoid = row["GEOID20"].strip()
        pop = int(row["TOTPOP"])

        if len(geoid) != 15 or not geoid.startswith("37"):
            raise ValueError(f"Invalid block ID: {geoid}")

        if geoid in population:
            raise ValueError(f"Duplicate population block: {geoid}")

        if pop < 0:
            raise ValueError(f"Negative population: {geoid}")

        population[geoid] = pop

pop_total = sum(population.values())

if len(population) != EXPECTED_BLOCKS:
    raise ValueError("Unexpected population block count")

if pop_total != EXPECTED_POPULATION:
    raise ValueError("Population total mismatch")

print(f"Population blocks: {len(population):,}")
print(f"Total population: {pop_total:,}")

print("\nJoining 2024 presidential election results...")

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
temporary = OUTPUT.with_suffix(".tmp")

seen = set()
harris_total = 0
trump_total = 0

try:
    with ZipFile(ELECTION_ZIP) as archive:
        with archive.open("nc_2024_gen_2020_blocks.csv") as raw:
            with io.TextIOWrapper(
                raw, encoding="utf-8-sig", newline=""
            ) as file:
                reader = csv.reader(file)
                header = next(reader)

                required = [
                    "GEOID20",
                    "PRECINCTID",
                    "G24PREDHAR",
                    "G24PRERTRU",
                ]

                missing = [c for c in required if c not in header]
                if missing:
                    raise ValueError(f"Missing election columns: {missing}")

                idx = {name: header.index(name) for name in required}

                with temporary.open(
                    "w", newline="", encoding="utf-8"
                ) as out:
                    writer = csv.writer(out)
                    writer.writerow([
                        "GEOID20",
                        "COUNTYFP",
                        "PRECINCTID",
                        "TOTPOP",
                        "G24PREDHAR",
                        "G24PRERTRU",
                    ])

                    for row in reader:
                        geoid = row[idx["GEOID20"]].strip()
                        precinct = row[idx["PRECINCTID"]].strip()

                        if geoid in seen:
                            raise ValueError(f"Duplicate election block: {geoid}")

                        if geoid not in population:
                            raise ValueError(f"Unmatched election block: {geoid}")

                        if not precinct:
                            raise ValueError(f"Missing precinct for {geoid}")

                        harris = int(row[idx["G24PREDHAR"]])
                        trump = int(row[idx["G24PRERTRU"]])

                        if harris < 0 or trump < 0:
                            raise ValueError(f"Negative votes in {geoid}")

                        seen.add(geoid)
                        harris_total += harris
                        trump_total += trump

                        writer.writerow([
                            geoid,
                            geoid[2:5],
                            precinct,
                            population[geoid],
                            harris,
                            trump,
                        ])

    if len(seen) != EXPECTED_BLOCKS:
        raise ValueError("Election block count mismatch")

    if set(population) != seen:
        raise ValueError("Census and election block IDs differ")

    if harris_total != EXPECTED_HARRIS:
        raise ValueError("Harris vote total mismatch")

    if trump_total != EXPECTED_TRUMP:
        raise ValueError("Trump vote total mismatch")

    temporary.replace(OUTPUT)

except Exception:
    temporary.unlink(missing_ok=True)
    raise

print(f"Matched blocks: {len(seen):,}")
print(f"Harris votes: {harris_total:,}")
print(f"Trump votes: {trump_total:,}")
print("NC election join validation passed")
print(f"Saved to: {OUTPUT}")
