"""RDH connector tests without network or credentials."""

import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.data import rdh_client as rdh

CATALOG_SAMPLE = (
    b'Title,Format,URL\n'
    b'2024 General Election Precinct-Level Results,CSV,'
    b'https://redistrictingdatahub.org/wp-json/download/file/PA%2Felection.zip?username=TOPSECRET&password=LEAKME&datasetid=12345\n'
)


class FakeResponse(io.BytesIO):
    pass


class RDHClientTests(unittest.TestCase):
    def test_safe_catalog_drops_credentials(self):
        records = rdh.parse_catalog_csv(CATALOG_SAMPLE)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["filename"], "election.zip")
        self.assertEqual(records[0]["dataset_id"], "12345")
        self.assertNotIn("TOPSECRET", json.dumps(records))
        self.assertNotIn("LEAKME", json.dumps(records))

    def test_catalog_rejects_external_host(self):
        row = {"Title": "Bad", "Format": "ZIP", "URL": "https://attacker.test/wp-json/download/file/hack.zip?datasetid=1"}
        self.assertIsNone(rdh._safe_entry(row))

    def test_catalog_rejects_path_traversal(self):
        row = {"Title": "Bad", "Format": "ZIP", "URL": "https://redistrictingdatahub.org/wp-json/download/file/%2E%2E%2Fhack.zip?datasetid=1"}
        self.assertIsNone(rdh._safe_entry(row))

    def test_catalog_rejects_missing_dataset_id(self):
        row = {"Title": "Bad", "Format": "ZIP", "URL": "https://redistrictingdatahub.org/wp-json/download/file/file.zip"}
        self.assertIsNone(rdh._safe_entry(row))

    def test_missing_credentials_sanitized(self):
        with patch.dict(rdh.os.environ, {}, clear=True):
            with self.assertRaisesRegex(rdh.RDHError, "credentials missing"):
                rdh.credentials()

    def test_inventory_mocks_network_and_stores_clean_catalog(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "catalog.json"
            with patch.object(rdh, "CATALOG", path), patch.object(rdh, "fetch_catalog", return_value=rdh.parse_catalog_csv(CATALOG_SAMPLE)):
                out = io.StringIO()
                with redirect_stdout(out):
                    self.assertEqual(rdh.inventory(query="2024"), 0)
                saved = path.read_text(encoding="utf-8")
                self.assertNotIn("TOPSECRET", saved)
                self.assertNotIn("LEAKME", saved)
                self.assertIn("2024 General Election", out.getvalue())

    def test_download_requires_cached_catalog(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(rdh, "CATALOG", Path(temp) / "catalog.json"):
                with self.assertRaisesRegex(rdh.RDHError, "No Pennsylvania RDH catalog"):
                    rdh.download("file.zip", dry_run=True)

    def test_download_dry_run_never_uses_network(self):
        with tempfile.TemporaryDirectory() as temp:
            catalog = Path(temp) / "catalog.json"
            entry = rdh.parse_catalog_csv(CATALOG_SAMPLE)[0]
            catalog.write_text(json.dumps({"state": "Pennsylvania", "files": [entry]}), encoding="utf-8")
            with patch.object(rdh, "CATALOG", catalog), patch.object(rdh, "_get", side_effect=AssertionError("network used")):
                self.assertEqual(rdh.download("election.zip", dry_run=True), 0)

    def test_download_produces_sha_receipt_without_credentials(self):
        with tempfile.TemporaryDirectory() as temp:
            catalog = Path(temp) / "catalog.json"
            entry = rdh.parse_catalog_csv(CATALOG_SAMPLE)[0]
            catalog.write_text(json.dumps({"state": "Pennsylvania", "files": [entry]}), encoding="utf-8")
            with patch.object(rdh, "CATALOG", catalog), patch.object(rdh, "_get", return_value=FakeResponse(b"example data")), patch.dict(rdh.os.environ, {"RDH_USERNAME": "tester", "RDH_PASSWORD": "secret"}):
                self.assertEqual(rdh.download("election.zip"), 0)
            receipt = json.loads((Path(temp) / "election.zip.receipt.json").read_text())
            self.assertEqual(receipt["status"], "DOWNLOADED_NOT_VALIDATED")
            self.assertEqual(receipt["bytes"], len(b"example data"))
            self.assertNotIn("secret", json.dumps(receipt))
            self.assertEqual((Path(temp) / "election.zip").read_bytes(), b"example data")

    def test_source_checklist_is_offline(self):
        with patch.object(rdh, "_get", side_effect=AssertionError("network used")):
            with redirect_stdout(io.StringIO()):
                self.assertEqual(rdh.run_pennsylvania("sources"), 0)


if __name__ == "__main__":
    unittest.main()
