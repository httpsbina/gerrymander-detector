"""Compare NC's 2023 and 2025 congressional plans using 2024 votes."""

import csv
import io
from collections import defaultdict
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data/raw/nc"
PROCESSED = ROOT / "data/processed"
SOURCE = PROCESSED / "nc_blocks_election.csv"
MASTER = PROCESSED / "nc_blocks_master.csv"
SUMMARY = PROCESSED / "nc_plan_comparison.csv"

PLAN_FILES = {
    2023: ("nc_cong_adopted_2023.zip", "SL 2023-145.csv"),
    2025: ("nc_cong_adopted_2025.zip", "NCGA_CCM-2 .csv"),
}

EXPECTED_BLOCKS = 236_638
EXPECTED_POP = 10_439_388
EXPECTED_HARRIS = 2_713_609
EXPECTED_TRUMP = 2_896_942
DISTRICTS = set(range(1, 15))


def load_plan(year):
    zip_name, csv_name = PLAN_FILES[year]
    assignments = {}

    with ZipFile(RAW / zip_name) as archive:
        with archive.open(csv_name) as raw:
            reader = csv.DictReader(
                io.TextIOWrapper(raw, encoding="utf-8-sig")
            )

            if not {"Block", "District"} <= set(reader.fieldnames or []):
                raise ValueError(f"{year}: missing columns")

            for row in reader:
                block = row["Block"].strip()
                district = int(row["District"])

                if len(block) != 15 or not block.startswith("37"):
                    raise ValueError(f"Invalid block: {block}")

                if district not in DISTRICTS:
                    raise ValueError(f"Invalid district: {district}")

                if block in assignments:
                    raise ValueError(f"Duplicate block: {block}")

                assignments[block] = district

    if len(assignments) != EXPECTED_BLOCKS:
        raise ValueError(f"{year}: block count mismatch")

    if set(assignments.values()) != DISTRICTS:
        raise ValueError(f"{year}: district count mismatch")

    print(f"{year}: {len(assignments):,} blocks, 14 districts")
    return assignments


plans = {year: load_plan(year) for year in PLAN_FILES}

if set(plans[2023]) != set(plans[2025]):
    raise ValueError("Congressional plans have different blocks")

stats = {
    year: defaultdict(lambda: [0, 0, 0, 0])
    for year in plans
}

seen = set()
total_pop = total_harris = total_trump = changed = 0

master_tmp = MASTER.with_suffix(".tmp")
summary_tmp = SUMMARY.with_suffix(".tmp")

try:
    with SOURCE.open(newline="", encoding="utf-8-sig") as source, \
         master_tmp.open("w", newline="", encoding="utf-8") as target:

        reader = csv.DictReader(source)

        required = {
            "GEOID20", "COUNTYFP", "PRECINCTID",
            "TOTPOP", "G24PREDHAR", "G24PRERTRU"
        }

        if not required <= set(reader.fieldnames or []):
            raise ValueError("Missing election columns")

        writer = csv.writer(target)
        writer.writerow([
            "GEOID20", "COUNTYFP", "PRECINCTID",
            "TOTPOP", "G24PREDHAR", "G24PRERTRU",
            "DISTRICT_2023", "DISTRICT_2025"
        ])

        for row in reader:
            block = row["GEOID20"].strip()

            if block in seen:
                raise ValueError(f"Duplicate block: {block}")

            if block not in plans[2023]:
                raise ValueError(f"Unmatched block: {block}")

            pop = int(row["TOTPOP"])
            harris = int(row["G24PREDHAR"])
            trump = int(row["G24PRERTRU"])

            if min(pop, harris, trump) < 0:
                raise ValueError(f"Negative value: {block}")

            seen.add(block)
            total_pop += pop
            total_harris += harris
            total_trump += trump

            d23 = plans[2023][block]
            d25 = plans[2025][block]
            changed += d23 != d25

            writer.writerow([
                block, row["COUNTYFP"], row["PRECINCTID"],
                pop, harris, trump, d23, d25
            ])

            for year, district in ((2023, d23), (2025, d25)):
                s = stats[year][district]
                s[0] += 1
                s[1] += pop
                s[2] += harris
                s[3] += trump

    if seen != set(plans[2023]) or len(seen) != EXPECTED_BLOCKS:
        raise ValueError("Block coverage mismatch")

    if (total_pop, total_harris, total_trump) != (
        EXPECTED_POP, EXPECTED_HARRIS, EXPECTED_TRUMP
    ):
        raise ValueError("Statewide totals mismatch")

    with summary_tmp.open(
        "w", newline="", encoding="utf-8"
    ) as target:
        writer = csv.writer(target)
        writer.writerow([
            "plan_year", "district", "blocks", "population",
            "harris_votes", "trump_votes",
            "harris_two_party_share", "presidential_winner",
            "population_deviation_pct"
        ])

        ideal_pop = total_pop / 14

        for year in sorted(stats):
            dem_seats = 0
            rep_seats = 0

            for district in sorted(DISTRICTS):
                blocks, pop, harris, trump = stats[year][district]

                if blocks == 0:
                    raise ValueError(f"Empty district: {district}")

                if harris > trump:
                    winner = "Harris"
                    dem_seats += 1
                elif trump > harris:
                    winner = "Trump"
                    rep_seats += 1
                else:
                    winner = "Tie"

                votes = harris + trump
                share = harris / votes if votes else 0

                writer.writerow([
                    year, district, blocks, pop, harris, trump,
                    round(share, 6), winner,
                    round(100 * (pop / ideal_pop - 1), 6)
                ])

            print(
                f"{year}: {dem_seats} Harris-won, "
                f"{rep_seats} Trump-won districts"
            )

    master_tmp.replace(MASTER)
    summary_tmp.replace(SUMMARY)

except Exception:
    master_tmp.unlink(missing_ok=True)
    summary_tmp.unlink(missing_ok=True)
    raise

print(f"Blocks reassigned between plans: {changed:,}")
print(f"Saved: {MASTER}")
print(f"Saved: {SUMMARY}")
print("NC congressional plan comparison passed validation")
