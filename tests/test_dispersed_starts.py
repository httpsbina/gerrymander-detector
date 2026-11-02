"""Dispersed-start selection and independent tree initialization fixtures."""

import unittest

from gerrychain import Graph
import networkx as nx
import numpy as np

from src.data_prep.generate_tree_start import generate
from src.data_prep.prepare_dispersed_texas_starts import maximin_indices


class DispersedStartTests(unittest.TestCase):
    def test_maximin_ordering_is_population_based_and_deterministic(self):
        maps=[np.array([0,0,1,1]),np.array([0,1,0,1]),np.array([0,0,0,1])]
        self.assertEqual(maximin_indices(maps,np.ones(4),3,0),[0,1,2])

    def test_duplicate_population_partitions_do_not_count_as_dispersed(self):
        maps=[np.array([0,0,1,1]),np.array([5,5,9,9])]
        with self.assertRaisesRegex(ValueError,'Insufficient distinct'):
            maximin_indices(maps,np.ones(4),2,0)

    def graph(self,zero=False):
        g=nx.convert_node_labels_to_integers(nx.grid_2d_graph(4,4))
        nx.set_node_attributes(g,1,'population')
        if zero:g.add_node(16,population=0);g.add_edge(0,16)
        return Graph.from_networkx(g)

    def test_tree_initialization_is_reproducible_and_balanced(self):
        a,p=generate(self.graph(),['01','02','03','04'],'population',0.001,40009,max_attempts=1000)
        b,q=generate(self.graph(),['01','02','03','04'],'population',0.001,40009,max_attempts=1000)
        self.assertEqual(a,b);self.assertEqual(p,q)
        self.assertEqual(set(p.values()),{4})

    def test_tree_initialization_preserves_zero_population_units(self):
        g=self.graph(zero=True)
        assignment,populations=generate(g,['01','02','03','04'],'population',0.001,40013,max_attempts=1000)
        self.assertEqual(set(assignment),set(range(17)))
        self.assertEqual(set(populations.values()),{4})
