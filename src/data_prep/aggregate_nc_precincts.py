"""Aggregate NC block data to precincts and audit geographic IDs."""

import csv
import struct
from collections import defaultdict
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[2]
MASTER = ROOT / "data/processed/nc_blocks_master.csv"
OUTPUT = ROOT / "data/processed/nc_precinct_aggregates.csv"
SHAPES = ROOT / "data/raw/nc/nc_2024_gen_prec.zip"

EXPECTED_BLOCKS = 236_638
EXPECTED_POP = 10_439_388
EXPECTED_HARRIS = 2_713_609
EXPECTED_TRUMP = 2_896_942

precincts = defaultdict(lambda: {
    "blocks": 0, "pop": 0, "harris": 0, "trump": 0,
    "d23": set(), "d25": set()
})

seen = set()
totals = [0, 0, 0]

print("Aggregating Census blocks to precincts...")

with MASTER.open(newline="", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)

    for row in reader:
        geoid = row["GEOID20"]
        precinct_id = row["PRECINCTID"]

        if geoid in seen:
            raise ValueError(f"Duplicate block: {geoid}")
        if not precinct_id:
            raise ValueError(f"Missing precinct ID: {geoid}")

        seen.add(geoid)

        pop = int(row["TOTPOP"])
        dem = int(row["G24PREDHAR"])
        rep = int(row["G24PRERTRU"])

        if min(pop, dem, rep) < 0:
            raise ValueError(f"Negative value: {geoid}")

        p = precincts[precinct_id]
        p["blocks"] += 1
        p["pop"] += pop
        p["harris"] += dem
        p["trump"] += rep
        p["d23"].add(int(row["DISTRICT_2023"]))
        p["d25"].add(int(row["DISTRICT_2025"]))

        totals[0] += pop
        totals[1] += dem
        totals[2] += rep

if len(seen) != EXPECTED_BLOCKS:
    raise ValueError("Block count mismatch")

if tuple(totals) != (
    EXPECTED_POP, EXPECTED_HARRIS, EXPECTED_TRUMP
):
    raise ValueError("Statewide totals mismatch")

print(f"Blocks: {len(seen):,}")
print(f"Precinct groups: {len(precincts):,}")

# Read the precinct identifiers directly from the shapefile DBF.
shape_ids = set()

with ZipFile(SHAPES) as archive:
    path = "nc_2024_gen_all_prec/nc_2024_gen_all_prec.dbf"

    with archive.open(path) as dbf:
        header = dbf.read(32)
        count, header_size, record_size = struct.unpack(
            "<IHH", header[4:12]
        )

        offset = 1
        id_field = None

        for _ in range((header_size - 33) // 32):
            field = dbf.read(32)
            name = field[:11].split(b"\x00")[0].decode("ascii")
            width = field[16]

            if name == "UNIQUE_ID":
                id_field = (offset, width)

            offset += width

        dbf.read(1)

        if id_field is None:
            raise ValueError("Missing UNIQUE_ID")

        start, width = id_field

        for _ in range(count):
            record = dbf.read(record_size)
            if len(record) != record_size:
                raise ValueError("Incomplete DBF record")

            identifier = record[
                start:start + width
            ].decode("ascii").strip()

            if identifier in shape_ids:
                raise ValueError(f"Duplicate geometry ID: {identifier}")

            shape_ids.add(identifier)

missing_geometry = sorted(set(precincts) - shape_ids)
missing_data = sorted(shape_ids - set(precincts))

print(f"Geometry precincts: {len(shape_ids):,}")
print(f"IDs missing geometry: {len(missing_geometry)}")
print(f"IDs missing block data: {len(missing_data)}")

for name in missing_geometry:
    print(f"  Block-only ID: {name}")

for name in missing_data:
    print(f"  Geometry-only ID: {name}")

OUTPUT.parent.mkdir(parents=True, exist_ok=True)

with OUTPUT.open("w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow([
        "PRECINCTID", "BLOCK_COUNT", "TOTPOP",
        "G24PREDHAR", "G24PRERTRU",
        "C23_NDIST", "C25_NDIST",
        "C23_DISTRICT", "C25_DISTRICT"
    ])

    for precinct_id, p in sorted(precincts.items()):
        writer.writerow([
            precinct_id,
            p["blocks"], p["pop"],
            p["harris"], p["trump"],
            len(p["d23"]), len(p["d25"]),
            next(iter(p["d23"])) if len(p["d23"]) == 1 else "",
            next(iter(p["d25"])) if len(p["d25"]) == 1 else ""
        ])

split23 = sum(len(p["d23"]) > 1 for p in precincts.values())
split25 = sum(len(p["d25"]) > 1 for p in precincts.values())

print(f"2023 split precinct groups: {split23}")
print(f"2025 split precinct groups: {split25}")
print(f"Population preserved: {totals[0]:,}")
print(f"Harris votes preserved: {totals[1]:,}")
print(f"Trump votes preserved: {totals[2]:,}")
print(f"Saved: {OUTPUT}")
print("Precinct aggregation validated; geometry reconciliation pending")
