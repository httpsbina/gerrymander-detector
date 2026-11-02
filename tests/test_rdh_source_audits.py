"""Scientific input failures tested with synthetic records, outside research paths."""

import csv
import io
from pathlib import Path
import struct
import tempfile
import unittest
from zipfile import ZipFile

from src.validation.audit_rdh_sources import read_plan, read_population, read_votes
from src.analysis.audit_enacted_election_sensitivity import swing_seats

try:
    import geopandas as gpd
    from shapely.geometry import Polygon, box
    from src.validation.audit_rdh_geometry import inspect_geometry
except ModuleNotFoundError:
    gpd = None


class SourceAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def csv_zip(self, name, rows):
        path = self.root / name
        text = io.StringIO()
        writer = csv.DictWriter(text, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
        with ZipFile(path, "w") as archive:
            archive.writestr("fixture.csv", text.getvalue())
        return path

    def test_votes_reject_duplicate_and_nonfinite_allocations(self):
        row = dict(GEOID20="370010201001000", PRECINCTID="fixture",
                   G24PREDHAR="1", G24PRERTRU="2")
        path = self.csv_zip("duplicate.zip", [row, row])
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            read_votes(path, "fixture.csv", "37")
        for value in ("nan", "inf", "-1", "0.5"):
            with self.subTest(value=value):
                invalid = dict(row, G24PREDHAR=value)
                path = self.csv_zip("invalid.zip", [invalid])
                with self.assertRaises(ValueError):
                    read_votes(path, "fixture.csv", "37")

    def test_plan_rejects_wrong_state_duplicate_and_missing_district(self):
        for rows in (
            [dict(Block="480010201001000", District=1)],
            [dict(Block="370010201001000", District=1)] * 2,
            [dict(Block="370010201001000", District=1)],
        ):
            with self.subTest(rows=rows):
                path = self.csv_zip("plan.zip", rows)
                with self.assertRaises(ValueError):
                    read_plan(path, "37", 2)

    def population_zip(self, values):
        header = bytearray(32)
        header_size, record_size = 97, 24
        header[4:12] = struct.pack("<IHH", len(values), header_size, record_size)
        descriptors = []
        for name, width in (("GEOID20", 15), ("P0010001", 8)):
            descriptor = bytearray(32)
            descriptor[:len(name)] = name.encode("ascii")
            descriptor[11] = ord("C")
            descriptor[16] = width
            descriptors.append(descriptor)
        records = b"".join(b" " + geoid.encode("ascii") + str(pop).rjust(8).encode("ascii")
                           for geoid, pop in values)
        path = self.root / "population.zip"
        with ZipFile(path, "w") as archive:
            archive.writestr("fixture.dbf", bytes(header) + b"".join(descriptors) + b"\r" + records)
        return path

    def test_zero_population_blocks_are_preserved(self):
        values = [("370010201001000", 0), ("370010201001001", 3)]
        path = self.population_zip(values)
        self.assertEqual(read_population(path, "fixture.dbf", "37"), dict(values))

    def test_duplicate_population_blocks_fail(self):
        path = self.population_zip([("370010201001000", 0)] * 2)
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            read_population(path, "fixture.dbf", "37")

    def test_uniform_swing_preserves_ties_and_is_monotone(self):
        votes = [(50, 50), (49, 51), (90, 10)]
        self.assertEqual(swing_seats(votes, 0), 1)
        values = [swing_seats(votes, shift) for shift in (-0.03, 0, 0.03)]
        self.assertEqual(values, sorted(values))
        with self.assertRaises(ValueError):
            swing_seats([(0, 0)], 0)


@unittest.skipIf(gpd is None, "Scientific environment required for geometry fixtures")
class GeometryAuditTests(unittest.TestCase):
    def frame(self, shapes, assignments):
        return gpd.GeoDataFrame({"UNIQUE_ID": [str(i) for i in range(len(shapes))],
                                 "district": assignments}, geometry=shapes, crs="EPSG:5070")

    def test_disconnected_district_is_detected_without_dropping_isolates(self):
        frame = self.frame([box(0, 0, 1, 1), box(2, 0, 3, 1)], [1, 1])
        result = inspect_geometry(frame, "district")
        self.assertEqual(result["graph_nodes"], 2)
        self.assertEqual(result["graph_components"], 2)
        self.assertEqual(result["district_components"], {"1": 2})
        self.assertEqual(len(result["isolates"]), 2)

    def test_overlap_is_measured_and_geometry_is_unchanged(self):
        frame = self.frame([box(0, 0, 2, 1), box(1, 0, 3, 1)], [1, 2])
        before = frame.geometry.to_wkb().tolist()
        result = inspect_geometry(frame, "district")
        self.assertEqual(result["sum_pairwise_overlap_area_m2"], 1)
        self.assertEqual(frame.geometry.to_wkb().tolist(), before)
        self.assertFalse(result["research_ready"])

    def test_point_contact_is_not_rook_adjacency(self):
        frame = self.frame([box(0, 0, 1, 1), box(1, 1, 2, 2)], [1, 1])
        result = inspect_geometry(frame, "district")
        self.assertEqual(result["graph_edges"], 0)
        self.assertEqual(result["graph_components"], 2)

    def test_invalid_geometry_is_recorded_without_repair(self):
        bowtie = Polygon([(0, 0), (1, 1), (0, 1), (1, 0), (0, 0)])
        frame = self.frame([bowtie], [1])
        result = inspect_geometry(frame, "district")
        self.assertEqual(len(result["invalid"]), 1)
        self.assertFalse(frame.geometry.is_valid.iloc[0])

    def test_sliver_overlap_can_change_sampler_adjacency(self):
        from src.validation.audit_adjacency_sensitivity import compare
        frame = self.frame([box(0, 0, 1, 1), box(0.99999, 0.99999, 2, 2)], [1, 2])
        result = compare(frame)
        self.assertEqual(result["sampler_edges"], 1)
        self.assertEqual(result["boundary_edges"], 0)
        self.assertEqual(result["differences"][0]["shared_boundary_length_m"], 0)

    def test_convergence_diagnostics_detect_constant_chains(self):
        import numpy as np
        from src.analysis.audit_rebuild_campaign import diagnostics
        result = diagnostics(np.zeros((4, 1500)))
        self.assertFalse(result["all_finite"])
        self.assertIsNone(result["rank_split_rhat"])
        self.assertTrue(result["issues"])

    def test_convergence_diagnostics_on_independent_normal_reference(self):
        import numpy as np
        from src.analysis.audit_rebuild_campaign import diagnostics
        result = diagnostics(np.random.default_rng(712).normal(size=(4, 2000)))
        self.assertTrue(result["all_finite"], result["issues"])
        self.assertLess(result["rank_split_rhat"], 1.01)
        self.assertGreater(result["bulk_ess"], 1000)
        self.assertGreater(result["mcse_mean"], 0)

    def test_campaign_checkpoint_detects_source_parameter_and_endpoint_mismatches(self):
        from copy import deepcopy
        from types import SimpleNamespace
        import pandas as pd
        from src.analysis.audit_rebuild_campaign import check_final_checkpoint
        experiment = dict(steps=2, epsilon=0.005, node_repeats=2,
                          dataset_sha256="fixture-data", prefix="fixture")
        source = {"src/chain/run_ensemble.py": "fixture-runner",
                  "src/chain/checkpoint_integrity.py": "fixture-helper"}
        configuration = dict(state="fixture", sample_every=1, epsilon=0.005, node_repeats=2)
        provenance = dict(dataset_sha256="fixture-data", runner_sha256="fixture-runner",
                          checkpoint_code_sha256="fixture-helper", configuration=configuration)
        checkpoint = dict(version=2, seed=7, next_step=2, epsilon=0.005, node_repeats=2,
                          plan_hash="fixture-last", pythonhashseed="0", provenance=provenance)
        chain = SimpleNamespace(plan_hash=pd.Series(["fixture-first", "fixture-last"]))
        self.assertEqual(check_final_checkpoint(checkpoint, experiment, 7, chain, source), provenance)
        for key, value in (("plan_hash", "other"), ("next_step", 1), ("node_repeats", 3), ("pythonhashseed", "1")):
            invalid = deepcopy(checkpoint)
            invalid[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                check_final_checkpoint(invalid, experiment, 7, chain, source)
        invalid = deepcopy(checkpoint)
        invalid["provenance"]["dataset_sha256"] = "other"
        with self.assertRaises(ValueError):
            check_final_checkpoint(invalid, experiment, 7, chain, source)
