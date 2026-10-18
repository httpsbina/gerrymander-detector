"""Audit NC block-disaggregated votes against precinct source totals."""

import csv
import io
import struct
from collections import defaultdict
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[2]
BLOCK_ZIP = ROOT / "data/raw/nc/nc_2024_gen_2020_blocks_csv.zip"
PRECINCT_ZIP = ROOT / "data/raw/nc/nc_2024_gen_prec.zip"

block_votes = defaultdict(lambda: [0, 0])

with ZipFile(BLOCK_ZIP) as archive:
    with archive.open("nc_2024_gen_2020_blocks.csv") as raw:
        reader = csv.DictReader(
            io.TextIOWrapper(raw, encoding="utf-8-sig")
        )

        for row in reader:
            votes = block_votes[row["PRECINCTID"]]
            votes[0] += int(row["G24PREDHAR"])
            votes[1] += int(row["G24PRERTRU"])

precinct_votes = {}

with ZipFile(PRECINCT_ZIP) as archive:
    path = "nc_2024_gen_all_prec/nc_2024_gen_all_prec.dbf"

    with archive.open(path) as dbf:
        header = dbf.read(32)
        count, header_size, record_size = struct.unpack(
            "<IHH", header[4:12]
        )

        fields = {}
        offset = 1

        for _ in range((header_size - 33) // 32):
            descriptor = dbf.read(32)
            name = descriptor[:11].split(b"\x00")[0].decode("ascii")
            width = descriptor[16]
            fields[name] = (offset, width)
            offset += width

        if dbf.read(1) != b"\r" or offset != record_size:
            raise ValueError("Invalid precinct DBF layout")

        for _ in range(count):
            record = dbf.read(record_size)

            if len(record) != record_size or record[:1] != b" ":
                raise ValueError("Invalid precinct record")

            def get(name):
                start, width = fields[name]
                return record[start:start + width].decode("ascii").strip()

            precinct = get("UNIQUE_ID")

            if precinct in precinct_votes:
                raise ValueError(f"Duplicate geometry: {precinct}")

            precinct_votes[precinct] = [
                int(float(get("G24PREDHAR"))),
                int(float(get("G24PRERTRU"))),
            ]

block_ids = set(block_votes)
geometry_ids = set(precinct_votes)

print("IDs only in blocks:", sorted(block_ids - geometry_ids))
print("IDs only in geometry:", sorted(geometry_ids - block_ids))

for precinct in sorted(block_ids & geometry_ids):
    if block_votes[precinct] != precinct_votes[precinct]:
        print(
            "Vote mismatch:", precinct,
            "blocks:", block_votes[precinct],
            "geometry:", precinct_votes[precinct]
        )

combined = "WAKE-:-01-07 & WAKE-:-01-07A"
regular = "WAKE-:-01-07"
separate = "WAKE-:-01-07A"

residual = [
    p - b
    for p, b in zip(precinct_votes[regular], block_votes[regular])
]

check = [
    a + b
    for a, b in zip(residual, precinct_votes[separate])
]

print("Wake combined-block votes:", block_votes[combined])
print("Wake vote totals reconcile:", check == block_votes[combined])

block_totals = [
    sum(v[i] for v in block_votes.values()) for i in (0, 1)
]

geometry_totals = [
    sum(v[i] for v in precinct_votes.values()) for i in (0, 1)
]

print("Statewide block votes:", block_totals)
print("Statewide geometry votes:", geometry_totals)
print(
    "Remaining statewide difference:",
    [a - b for a, b in zip(block_totals, geometry_totals)]
)
