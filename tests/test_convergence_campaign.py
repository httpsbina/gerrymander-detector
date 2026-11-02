"""Continuation snapshot boundaries and fixed-screen control checks."""

import copy
from pathlib import Path
import tempfile
import unittest

from src.chain.convergence_state import ROOT, screening_status, snapshot_manifest


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name);self.source = self.root/'source'/'ensembles'
        self.source.mkdir(parents=True);(self.source.parent/'checkpoints').mkdir()

    def manifest(self, steps):
        return {'experiments':{'tx_rebuild':{'input_dir':str(self.source.relative_to(ROOT)),
                'prefix':'fixture','epsilon':0.001,'seeds':[7],'steps':steps}}}

    def segment(self, first, last):
        (self.source/f'fixture_chain_eps0p001_seed7_steps{first:06d}-{last:06d}.csv').write_text('fixture\n')

    def checkpoint(self, step):
        (self.source.parent/'checkpoints'/f'fixture_checkpoint_eps0p001_seed7_next{step}.pkl').write_bytes(b'fixture')

    def test_snapshot_is_stable_when_later_segments_arrive(self):
        self.segment(0,4);self.checkpoint(5)
        p=snapshot_manifest(self.manifest(5),self.root/'snapshot')
        self.segment(5,9)
        self.assertTrue(p.is_file())
        self.assertEqual(len(list((p.parent/'tx_rebuild'/'ensembles').glob('*.csv'))),1)

    def test_snapshot_refuses_gaps_and_overlaps(self):
        for first in (4,6):
            with self.subTest(first=first):
                for p in self.source.glob('*.csv'):p.unlink()
                self.segment(0,4);self.segment(first,9);self.checkpoint(10)
                with self.assertRaisesRegex(ValueError,'Missing or overlapping'):
                    snapshot_manifest(self.manifest(10),self.root/f'bad{first}')

    def test_snapshot_never_truncates_a_segment(self):
        self.segment(0,9);self.checkpoint(5)
        with self.assertRaisesRegex(ValueError,'cuts through'):
            snapshot_manifest(self.manifest(5),self.root/'bad')


class ScreeningTests(unittest.TestCase):
    def report(self):
        value={'all_finite':True,'screening_flags':[]}
        entry={'integrity':'pass','diagnostics':{'dem_seats':copy.deepcopy(value),'cut_edges':copy.deepcopy(value)}}
        joint={'status':'computed','diagnostics':copy.deepcopy(entry['diagnostics'])}
        bad={'integrity':'pass','diagnostics':{'dem_seats':{'all_finite':True,'screening_flags':['bulk ESS below 400']}}}
        return {'experiments':{'nc_block_union_2023':copy.deepcopy(entry),'nc_block_union_2025':copy.deepcopy(entry),'tx_rebuild':bad},'joint_nc':{'nc_block_union':joint}}

    def test_nc_target_excludes_unrelated_texas_failure(self):
        status=screening_status(self.report(),'north_carolina')
        self.assertTrue(status['seat_screen_pass']);self.assertTrue(status['all_primary_screens_pass'])

    def test_other_metric_or_nonfinite_failure_cannot_pass_primary_gate(self):
        for change in ('screen','nonfinite','integrity'):
            r=self.report();e=r['experiments']['nc_block_union_2023']
            if change=='screen':e['diagnostics']['cut_edges']['screening_flags']=['rank R-hat at or above 1.01']
            elif change=='nonfinite':e['diagnostics']['cut_edges']['all_finite']=False
            else:e['integrity']='fail'
            with self.subTest(change=change):self.assertFalse(screening_status(r,'north_carolina')['all_primary_screens_pass'])
