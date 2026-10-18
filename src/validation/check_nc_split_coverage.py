"""Audit block-level district assignments against NC precinct geometry."""

import csv
import re
import struct
from collections import defaultdict
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[2]
MASTER = ROOT / "data/processed/nc_blocks_master.csv"
SHAPES = ROOT / "data/raw/nc/nc_2024_gen_prec.zip"
DBF = "nc_2024_gen_cong_prec/nc_2024_gen_cong_prec.dbf"

block_districts = defaultdict(set)
seen_blocks = set()

with MASTER.open(newline="", encoding="utf-8-sig") as file:
    reader = csv.DictReader(file)
    needed = {"GEOID20", "PRECINCTID", "DISTRICT_2023"}

    if not needed <= set(reader.fieldnames or []):
        raise ValueError("Missing block master columns")

    for row in reader:
        block = row["GEOID20"].strip()
        precinct = row["PRECINCTID"].strip()
        district = int(row["DISTRICT_2023"])

        if block in seen_blocks:
            raise ValueError(f"Duplicate block: {block}")

        if not precinct or not 1 <= district <= 14:
            raise ValueError(f"Invalid precinct or district: {block}")

        seen_blocks.add(block)
        block_districts[precinct].add(district)

if len(seen_blocks) != 236_638:
    raise ValueError("Unexpected block count")

shape_members = defaultdict(list)
seen_shapes = set()

with ZipFile(SHAPES) as archive:
    with archive.open(DBF) as file:
        header = file.read(32)
        count, header_size, record_size = struct.unpack(
            "<IHH", header[4:12]
        )

        offset = 1
        id_field = None

        for _ in range((header_size - 33) // 32):
            descriptor = file.read(32)
            name = descriptor[:11].split(b"\x00")[0].decode("ascii")
            width = descriptor[16]

            if name == "UNIQUE_ID":
                id_field = (offset, width)

            offset += width

        if file.read(1) != b"\r" or offset != record_size:
            raise ValueError("Invalid DBF structure")

        if id_field is None:
            raise ValueError("Missing UNIQUE_ID")

        start, width = id_field

        for _ in range(count):
            record = file.read(record_size)

            if len(record) != record_size or record[:1] != b" ":
                raise ValueError("Invalid DBF record")

            name = record[start:start + width].decode("ascii").strip()

            if name in seen_shapes:
                raise ValueError(f"Duplicate geometry ID: {name}")

            seen_shapes.add(name)

            match = re.fullmatch(r"(.+)-\(CON-(\d{2})\)", name)
            base = match.group(1) if match else name
            district = int(match.group(2)) if match else None

            shape_members[base].append(district)

block_ids = set(block_districts)
geometry_ids = set(shape_members)

unrepresented = sorted(
    name for name in block_ids & geometry_ids
    if len(block_districts[name]) > 1
    and len(shape_members[name]) == 1
)

mismatched_splits = sorted(
    name for name in block_ids & geometry_ids
    if len(shape_members[name]) > 1
    and set(shape_members[name]) != block_districts[name]
)

print("Census blocks:", len(seen_blocks))
print("Block-data precinct groups:", len(block_ids))
print("Congressional precinct features:", len(seen_shapes))

print(
    "Precincts split in block assignments:",
    sum(len(v) > 1 for v in block_districts.values())
)

print(
    "Precincts split in geometry features:",
    sum(len(v) > 1 for v in shape_members.values())
)

print("Block-only precinct labels:", sorted(block_ids - geometry_ids))
print("Geometry-only precinct labels:", sorted(geometry_ids - block_ids))

print("Block-level splits without separate geometry features:")
for name in unrepresented:
    print(" ", name, "districts", sorted(block_districts[name]))

print(
    "Conflicting district labels on already split features:",
    mismatched_splits
)

print("Audit complete; unresolved cases require geometry review")
