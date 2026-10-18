"""Extract and validate North Carolina 2020 Census block population."""

import csv
import struct
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "data/raw/nc/nc_pl2020_b.zip"
OUTPUT = ROOT / "data/processed/nc_blocks_population.csv"

EXPECTED_BLOCKS = 236_638
EXPECTED_POPULATION = 10_439_388

print("Loading NC Census block population...")

with ZipFile(SOURCE) as archive:
    with archive.open("nc_pl2020_p1_b.dbf") as dbf:
        header = dbf.read(32)
        record_count, header_size, record_size = struct.unpack(
            "<IHH", header[4:12]
        )

        field_count = (header_size - 33) // 32
        fields = {}
        offset = 1

        for _ in range(field_count):
            field = dbf.read(32)
            name = field[:11].split(b"\x00")[0].decode("ascii")
            width = field[16]
            fields[name] = (offset, width)
            offset += width

        if dbf.read(1) != b"\r":
            raise ValueError("Invalid DBF header")

        if offset != record_size:
            raise ValueError("DBF record layout mismatch")

        for name in ("GEOID20", "P0010001"):
            if name not in fields:
                raise ValueError(f"Missing column: {name}")

        def get_value(record, name):
            start, width = fields[name]
            return record[start:start + width].decode("ascii").strip()

        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        temporary = OUTPUT.with_suffix(".tmp")

        seen = set()
        total_population = 0

        with temporary.open("w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(["GEOID20", "TOTPOP"])

            for _ in range(record_count):
                record = dbf.read(record_size)

                if len(record) != record_size or record[:1] != b" ":
                    raise ValueError("Invalid Census block record")

                geoid = get_value(record, "GEOID20")
                population = int(get_value(record, "P0010001"))

                if len(geoid) != 15 or not geoid.startswith("37"):
                    raise ValueError(f"Invalid NC block ID: {geoid}")

                if geoid in seen:
                    raise ValueError(f"Duplicate block: {geoid}")

                if population < 0:
                    raise ValueError(f"Negative population: {geoid}")

                seen.add(geoid)
                total_population += population
                writer.writerow([geoid, population])

        print(f"Blocks: {len(seen):,}")
        print(f"Population: {total_population:,}")

        if len(seen) != EXPECTED_BLOCKS:
            raise ValueError("Unexpected Census block count")

        if total_population != EXPECTED_POPULATION:
            raise ValueError("Population does not match 2020 Census")

        temporary.replace(OUTPUT)

print("NC population validation passed")
print(f"Saved to: {OUTPUT}")
