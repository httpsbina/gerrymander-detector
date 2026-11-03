"""Archive the working ARM Mac runtime for offline relocation and replay."""

import argparse
from importlib import metadata
import io
import json
from pathlib import Path
import platform
import sys
import tarfile

from src.chain.checkpoint_integrity import file_sha256

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.resolve().relative_to(ROOT)
    if args.output.exists():
        raise FileExistsError(args.output)
    runtime = Path(sys.base_prefix).resolve()
    runtime.relative_to(ROOT)
    packages = Path(sys.prefix) / "lib/python3.12/site-packages"
    packages.resolve().relative_to(ROOT)
    versions = {}
    for line in (ROOT / "requirements-research-macos-arm64-py312.txt").read_text().splitlines():
        if not line or line.startswith("#"):
            continue
        name, version = line.split("==")
        if metadata.version(name) != version:
            raise ValueError(f"Working package differs from pinned version: {name}")
        versions[name] = version
    script = '''#!/bin/sh
set -eu
cd "$(dirname "$0")"
if [ ! -x .venv/science/bin/python ]; then
  runtime/python/bin/python3.12 -m venv --without-pip .venv/science
  cp -R runtime/site-packages/. .venv/science/lib/python3.12/site-packages/
fi
if command -v caffeinate >/dev/null 2>&1; then
  exec caffeinate -i ./resume.sh "$@"
fi
exec ./resume.sh "$@"
'''
    record = {"python": sys.version, "platform": platform.platform(), "packages": versions,
              "scope": "Working standalone Python and installed scientific packages; no credentials or user configuration",
              "target_check": "Identical runtime profile and exact replay required on receiving machine"}
    receipts = {}
    with tarfile.open(args.output, "w:gz", dereference=False) as archive:
        for source, prefix in ((runtime, "runtime/python"), (packages, "runtime/site-packages")):
            for path in sorted(source.rglob("*")):
                if "__pycache__" in path.parts or path.suffix == ".pyc" or path.is_dir():
                    continue
                path.resolve().relative_to(source)
                name = str(Path(prefix) / path.relative_to(source))
                if path.is_symlink() and path.readlink().is_absolute():
                    raise ValueError("Absolute environment symlink cannot be relocated")
                receipts[name] = {"symlink": str(path.readlink())} if path.is_symlink() else {"sha256": file_sha256(path)}
                archive.add(path, arcname=name, recursive=False)
        record["files"] = receipts
        for name, content, mode in (("runtime/environment.json", json.dumps(record, indent=2) + "\n", 0o644),
                                    ("resume_offline.sh", script, 0o755)):
            data = content.encode()
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mode = mode
            archive.addfile(info, io.BytesIO(data))
    with args.output.with_suffix(".sha256").open("x") as stream:
        stream.write(file_sha256(args.output) + "  " + args.output.name + "\n")
    print(f"Archived {len(receipts)} environment files; {args.output.stat().st_size} bytes")


if __name__ == "__main__":
    main()
