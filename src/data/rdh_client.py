"""RDH Pennsylvania source discovery and controlled download.

No imports from the simulation code; source acquisition never certifies research
validity. Credentials are read only from process environment and are never
stored in catalog artifacts or printed by this module.
"""

import csv
import hashlib
import io
import json
import os
from pathlib import Path
import re
import sys
from urllib import error, parse, request

ROOT = Path(__file__).resolve().parents[2]
API_BASE = "https://redistrictingdatahub.org/wp-json/download"
CATALOG = ROOT / "data" / "external" / "rdh" / "pennsylvania" / "catalog.json"
SOURCE_CHECKLIST = ROOT / "configs" / "pennsylvania_sources.json"
MAX_CATALOG_BYTES = 15_000_000
MAX_FILE_BYTES = 2_000_000_000


class RDHError(Exception):
    """Safe error message: never include credential-bearing API URLs."""


def credentials():
    username = os.environ.get("RDH_USERNAME", "").strip()
    password = os.environ.get("RDH_PASSWORD", "")
    if not username or not password:
        raise RDHError(
            "RDH API credentials missing. Set RDH_USERNAME and RDH_PASSWORD "
            "as environment variables; designated API access is required. "
            "Do not paste credentials into chat or commit them."
        )
    return username, password


def _get(url, params):
    # The upstream RDH WordPress API requires credentials in query parameters.
    # NEVER log Request.full_url or the underlying urllib exception.
    full_url = url + "?" + parse.urlencode(params)
    try:
        return request.urlopen(
            request.Request(full_url, headers={"User-Agent": "GerrymanderDetectorResearch/1"}),
            timeout=90,
        )
    except error.HTTPError as exc:
        raise RDHError(
            f"RDH API returned HTTP {exc.code}; check API-user permission and request parameters."
        ) from None
    except (error.URLError, TimeoutError, OSError):
        raise RDHError("RDH API connection failed; check access or network connectivity.") from None


def _safe_entry(row):
    """Accept official RDH file links but never persist credential-bearing URLs."""
    title = (row.get("Title") or "").strip()
    fmt = (row.get("Format") or "").strip()
    raw_url = (row.get("URL") or "").strip()
    parts = parse.urlsplit(raw_url)
    prefix = "/wp-json/download/file/"
    if parts.scheme != "https" or parts.hostname != "redistrictingdatahub.org":
        return None
    if not parts.path.startswith(prefix):
        return None
    download_path = parts.path[len(prefix):]
    if not download_path or any(segment in (".", "..") for segment in parse.unquote(download_path).split("/")):
        return None
    dataset_ids = parse.parse_qs(parts.query).get("datasetid", [])
    if len(dataset_ids) != 1 or not re.fullmatch(r"[0-9A-Za-z_-]+", dataset_ids[0]):
        return None
    name = parse.unquote(download_path).replace("\\", "/").split("/")[-1]
    if not name or not re.fullmatch(r"[\w][\w.() +%,-]*", name):
        return None
    # A simple filename is saved locally; remote encoded subfolders stay in download_path.
    return {
        "title": title,
        "format": fmt,
        "filename": name,
        "dataset_id": dataset_ids[0],
        "download_path": download_path,
    }


def parse_catalog_csv(data):
    try:
        decoded = data.decode("utf-8-sig")
    except UnicodeError:
        raise RDHError("RDH returned a non-UTF-8 catalog") from None
    rows = list(csv.DictReader(io.StringIO(decoded)))
    if not rows or not {"Title", "Format", "URL"}.issubset(rows[0]):
        raise RDHError(
            "RDH response is not a valid dataset catalog. Check credentials and designated API-user access."
        )
    safe = [_safe_entry(row) for row in rows]
    return [x for x in safe if x is not None]


def fetch_catalog():
    username, password = credentials()
    with _get(API_BASE + "/list", {
        "username": username,
        "password": password,
        "format": "csv",
        "states": "Pennsylvania",
    }) as response:
        raw = response.read(MAX_CATALOG_BYTES + 1)
    if len(raw) > MAX_CATALOG_BYTES:
        raise RDHError("RDH catalog exceeded the size limit; contact the data provider")
    records = parse_catalog_csv(raw)
    if not records:
        raise RDHError("RDH returned no usable file URLs; confirm API permissions and response format")
    return records


def atomic_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    try:
        with temp.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def show_sources():
    with SOURCE_CHECKLIST.open(encoding="utf-8") as handle:
        content = json.load(handle)
    print("PENNSYLVANIA RESEARCH DATA REQUIREMENTS")
    print("=====================================")
    for entry in content["requirements"]:
        print(f"[{entry['status']}] {entry['name']}")
        print(f"  Purpose: {entry['purpose']}")
        print(f"  Source: {entry['source_url']}")
    print("All inputs are UNVERIFIED. No Pennsylvania analyses may run yet.")
    return 0


def inventory(query=None, dry_run=False):
    if dry_run:
        print("DRY RUN: would request the RDH Pennsylvania file catalog; no connection or file write")
        return 0
    records = fetch_catalog()
    payload = {
        "provider": "Redistricting Data Hub",
        "state": "Pennsylvania",
        "source_page": "https://redistrictingdatahub.org/state/pennsylvania/",
        "status": "UNVERIFIED; metadata catalog only",
        "files": records,
    }
    atomic_json(CATALOG, payload)
    query_lower = (query or "").casefold().strip()
    matching = [x for x in records if query_lower in (x["title"] + " " + x["format"]).casefold()]
    print(f"RDH CATALOG: {len(records)} entries saved locally")
    print(f"CATALOG: {CATALOG}")
    print(f"MATCHING FILTER: {len(matching)} entries")
    for x in matching[:30]:
        print(f"  {x['title']} [{x['format']}] -> {x['filename']}")
    if len(matching) > 30:
        print("  (output limited to 30 entries; full catalog saved)")
    print("This is a source inventory, not a validated statewide dataset.")
    return 0


def download(filename, dry_run=False):
    if not filename:
        raise RDHError("Download requires --rdh-file FILENAME copied from the catalog")
    if not CATALOG.is_file():
        raise RDHError("No Pennsylvania RDH catalog. Run --stage inventory first")
    with CATALOG.open(encoding="utf-8") as handle:
        catalog = json.load(handle)
    if catalog.get("state") != "Pennsylvania":
        raise RDHError("Wrong catalog state")
    matching = [x for x in catalog.get("files", []) if x.get("filename") == filename]
    if len(matching) != 1:
        raise RDHError(f"File selection must match exactly one catalog entry (found {len(matching)})")
    entry = matching[0]
    # Treat on-disk catalog as untrusted; re-validate provider/path/ID.
    validated = _safe_entry({
        "Title": entry.get("title", ""),
        "Format": entry.get("format", ""),
        "URL": API_BASE + "/file/" + entry["download_path"] + "?datasetid=" + entry["dataset_id"],
    })
    if validated is None or validated["filename"] != filename:
        raise RDHError("Unsafe or invalid RDH catalog entry")
    target = CATALOG.parent / filename
    if target.exists():
        raise RDHError(f"Refusing to overwrite existing download: {filename}")
    if dry_run:
        print(f"DRY RUN: would download RDH file '{filename}' to {target}")
        return 0
    username, password = credentials()
    source = API_BASE + "/file/" + validated["download_path"]
    params = {"username": username, "password": password, "datasetid": validated["dataset_id"]}
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name(target.name + ".partial")
    digest, total = hashlib.sha256(), 0
    try:
        with _get(source, params) as response, temp.open("xb") as output:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                if total == 0 and chunk[:128].lstrip().lower().startswith((b"<!doctype html", b"<html")):
                    raise RDHError("RDH returned an HTML page instead of a download; check credentials")
                total += len(chunk)
                if total > MAX_FILE_BYTES:
                    raise RDHError("RDH file exceeded the download safety limit")
                output.write(chunk)
                digest.update(chunk)
        if total == 0:
            raise RDHError("RDH returned an empty file")
        temp.replace(target)
    finally:
        temp.unlink(missing_ok=True)
    # Download receipts exclude URLs, usernames and passwords.
    receipt_path = target.with_name(target.name + ".receipt.json")
    atomic_json(receipt_path, {
        "source": "Redistricting Data Hub",
        "title": entry["title"],
        "dataset_id": entry["dataset_id"],
        "filename": filename,
        "bytes": total,
        "sha256": digest.hexdigest(),
        "status": "DOWNLOADED_NOT_VALIDATED",
    })
    print(f"DOWNLOADED: {target}\nBYTES: {total}\nSHA256: {digest.hexdigest()}")
    print("Research status: not validated; do not use for inference yet.")
    return 0


def run_pennsylvania(stage, query=None, filename=None, dry_run=False):
    try:
        if stage == "sources":
            if query or filename:
                raise RDHError("--rdh-filter / --rdh-file do not apply to sources")
            return show_sources()
        if stage == "inventory":
            if filename:
                raise RDHError("--rdh-file is only valid for download")
            return inventory(query=query, dry_run=dry_run)
        if stage == "download":
            if query:
                raise RDHError("--rdh-filter only applies to inventory")
            return download(filename, dry_run=dry_run)
        raise RDHError("Unsupported RDH stage")
    except (RDHError, ValueError, OSError, KeyError, json.JSONDecodeError):
        # Not exposing exception traces prevents credential-bearing exception URLs.
        exc = sys.exc_info()[1]
        if isinstance(exc, RDHError):
            print(f"ERROR: {exc}", file=sys.stderr)
        else:
            print("ERROR: RDH catalog or filesystem operation failed; check source and local data permissions", file=sys.stderr)
        return 2
