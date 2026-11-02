"""Generate one independent population-balanced starting assignment."""

import argparse
from functools import partial
import json
from pathlib import Path
import random
import sys
import time
import warnings

import geopandas as gpd
from gerrychain import Graph
from gerrychain.tree import bipartition_tree, random_spanning_tree, recursive_tree_part
import networkx as nx

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from src.chain.checkpoint_integrity import file_sha256
from src.data_prep.prepare_dispersed_texas_starts import plan_hash


def ordered_tree(graph):
    ordered=nx.Graph()
    ordered.add_nodes_from((node,dict(graph.nodes[node])) for node in sorted(graph.nodes))
    ordered.add_edges_from(sorted(tuple(sorted(edge)) for edge in graph.edges))
    return random_spanning_tree(ordered)


def generate(graph, parts, population_column, epsilon, seed, max_attempts=10000):
    random.seed(seed)
    total=sum(graph.nodes[i][population_column] for i in graph.nodes)
    assignment=recursive_tree_part(graph,parts=parts,pop_target=total/len(parts),pop_col=population_column,
        epsilon=epsilon,node_repeats=2,method=partial(bipartition_tree,spanning_tree_fn=ordered_tree,max_attempts=max_attempts))
    if set(assignment)!=set(graph.nodes):raise ValueError('Incomplete initialization assignment')
    populations={part:sum(graph.nodes[i][population_column] for i in graph.nodes if assignment[i]==part) for part in parts}
    if any(abs(pop/(total/len(parts))-1)>epsilon+1e-10 for pop in populations.values()):raise ValueError('Population bounds failed')
    if any(not nx.is_connected(graph.subgraph([i for i in graph.nodes if assignment[i]==part])) for part in parts):raise ValueError('Disconnected starting district')
    return assignment,populations


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--seed',type=int,required=True)
    parser.add_argument('--epsilon',type=float,default=0.001)
    parser.add_argument('--districts',type=int,default=38)
    args=parser.parse_args()
    for p in (args.dataset,args.output_dir):p.resolve().relative_to(ROOT)
    args.output_dir.mkdir(parents=True,exist_ok=False)
    started=time.monotonic()
    frame=gpd.read_file(args.dataset,layer='precincts')
    with warnings.catch_warnings(record=True):graph=Graph.from_geodataframe(frame,adjacency='rook',cols_to_add=['TOTPOP'])
    try:
        assignment,populations=generate(graph,[f'{i:02d}' for i in range(1,args.districts+1)],'TOTPOP',args.epsilon,args.seed)
        report={'kind':'independent_recursive_tree_start','generation_seed':args.seed,'dataset_sha256':file_sha256(args.dataset),
            'epsilon':args.epsilon,'districts':args.districts,'assignment':{str(i):d for i,d in assignment.items()},
            'plan_hash':plan_hash(graph,assignment),'district_populations':populations,'seconds':time.monotonic()-started,
            'all_districts_graph_contiguous':True,'initialization_tree_attempt_limit':10000,'code_sha256':file_sha256(__file__)}
        with (args.output_dir/'assignment.json').open('x') as stream:json.dump(report,stream,indent=2);stream.write('\n')
        print(json.dumps({k:v for k,v in report.items() if k!='assignment'}),flush=True)
    except Exception as exc:
        with (args.output_dir/'failure.json').open('x') as stream:json.dump({'generation_seed':args.seed,'seconds':time.monotonic()-started,'error':f'{type(exc).__name__}: {exc}'},stream,indent=2);stream.write('\n')
        raise


if __name__=='__main__':main()
