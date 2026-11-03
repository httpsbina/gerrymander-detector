"""Select population-based dispersed starts without changing the Texas sampler."""

import argparse
import copy
import hashlib
import json
from pathlib import Path
import pickle
import sys
import warnings
from types import SimpleNamespace

import geopandas as gpd
from gerrychain import Graph
import networkx as nx
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.analysis.audit_partition_distances import partition_distances
from src.chain.checkpoint_integrity import file_sha256, provenance


def plan_hash(graph, assignment):
    edges = sorted(tuple(sorted((str(a), str(b)))) for a,b in graph.edges if assignment[a] != assignment[b])
    return hashlib.sha256('|'.join(f'{a}:{b}' for a,b in edges).encode()).hexdigest()


def kernel_signature(frame, graph):
    rows = [(int(i),str(frame.UNIQUE_ID.iloc[i]),int(frame.TOTPOP.iloc[i]),int(frame.G24PREDHAR.iloc[i]),int(frame.G24PRERTRU.iloc[i])) for i in range(len(frame))]
    edges = sorted(tuple(sorted((int(a),int(b)))) for a,b in graph.edges)
    return hashlib.sha256(json.dumps({'nodes':rows,'edges':edges},separators=(',',':')).encode()).hexdigest()


def maximin_indices(assignments, population, count, anchor):
    if count < 1 or count > len(assignments) or not 0 <= anchor < len(assignments):
        raise ValueError('Invalid dispersed-start selection size or anchor')
    selected = [anchor]
    distances = np.full(len(assignments), np.inf)
    while len(selected) < count:
        latest = selected[-1]
        for i, candidate in enumerate(assignments):
            if i not in selected:
                distances[i] = min(distances[i], partition_distances(assignments[latest],candidate,population)[1])
        distances[selected] = -np.inf
        index = int(np.argmax(distances))
        if distances[index] <= 0:raise ValueError('Insufficient distinct population partitions for requested starts')
        selected.append(index)
    return selected


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-manifest',type=Path,required=True)
    parser.add_argument('--registry',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--seeds',type=int,nargs=4,required=True)
    parser.add_argument('--independent-pool',type=Path,nargs=4)
    args=parser.parse_args()
    for p in (args.source_manifest,args.registry,args.output_dir):p.resolve().relative_to(ROOT)
    if len(set(args.seeds)) != 4:raise ValueError('Four distinct new seeds required')
    source=json.loads(args.source_manifest.read_text());original=source['experiments']['tx_rebuild']
    if set(args.seeds)&set(original['seeds']):raise ValueError('New seeds overlap the original baseline')
    dataset=(ROOT/original['dataset']).resolve();dataset.relative_to(ROOT)
    if file_sha256(dataset)!=original['dataset_sha256']:raise ValueError('Original dataset changed')
    folder=args.output_dir.resolve();folder.mkdir(parents=True,exist_ok=False)
    frame=gpd.read_file(dataset,layer='precincts')
    columns=['TOTPOP','G24PREDHAR','G24PRERTRU','CONG_DIST']
    with warnings.catch_warnings(record=True) as captured:
        graph=Graph.from_geodataframe(frame,adjacency='rook',cols_to_add=columns)
    candidates=[];assignments=[]
    directory=(ROOT/original['input_dir']).resolve().parent/'checkpoints';directory.relative_to(ROOT)
    for seed in original['seeds']:
        if args.independent_pool:break
        for next_step in range(100,original['steps']+1,100):
            if next_step-1<original['warmup']:continue
            p=directory/f"{original['prefix']}_checkpoint_eps0p001_seed{seed}_next{next_step}.pkl"
            with p.open('rb') as stream:c=pickle.load(stream)
            if (c['version']!=2 or c['next_step']!=next_step or c['seed']!=seed
                    or c['provenance']['dataset_sha256']!=original['dataset_sha256']
                    or c['provenance']['runner_sha256']!=source['source_code']['src/chain/run_ensemble.py']
                    or set(c['assignment'])!=set(graph.nodes)):
                raise ValueError('Candidate checkpoint provenance mismatch')
            if plan_hash(graph,c['assignment'])!=c['plan_hash']:raise ValueError('Candidate fingerprint mismatch')
            assignments.append(np.asarray([c['assignment'][i] for i in frame.index]))
            candidates.append({'source_seed':seed,'source_step':next_step-1,'checkpoint':str(p.relative_to(ROOT)),
                               'checkpoint_sha256':file_sha256(p),'plan_hash':c['plan_hash']})
    if args.independent_pool:
        for path in args.independent_pool:
            path.resolve().relative_to(ROOT)
            record=json.loads(path.read_text())
            if record['kind']!='independent_recursive_tree_start' or record['dataset_sha256']!=original['dataset_sha256'] or record['epsilon']!=original['epsilon']:
                raise ValueError('Independent initialization source mismatch')
            assignment={int(i):d for i,d in record['assignment'].items()}
            if set(assignment)!=set(graph.nodes) or plan_hash(graph,assignment)!=record['plan_hash']:
                raise ValueError('Independent initialization coverage or fingerprint mismatch')
            assignments.append(np.asarray([assignment[i] for i in frame.index]))
            candidates.append({'generation_seed':record['generation_seed'],'assignment_file':str(path.resolve().relative_to(ROOT)),
                               'assignment_sha256':file_sha256(path),'plan_hash':record['plan_hash']})
        if len({c['generation_seed'] for c in candidates})!=4:raise ValueError('Independent generation seeds must differ')
        anchor=min(range(len(candidates)),key=lambda i:candidates[i]['generation_seed'])
    else:
        anchor=next(i for i,c in enumerate(candidates) if c['source_seed']==min(original['seeds']) and c['source_step']==original['steps']-1)
    selected=maximin_indices(assignments,frame.TOTPOP.to_numpy(),4,anchor)
    new_dataset=folder/'tx_dispersed_starts.gpkg'
    prepared=frame.copy()
    for seed,index in zip(args.seeds,selected):prepared[f'START_{seed}']=assignments[index]
    prepared.to_file(new_dataset,layer='precincts',driver='GPKG')
    rebuilt=gpd.read_file(new_dataset,layer='precincts')
    if rebuilt.UNIQUE_ID.tolist()!=frame.UNIQUE_ID.tolist():raise ValueError('Unit ordering changed')
    if rebuilt[columns].to_dict('list')!=frame[columns].to_dict('list'):raise ValueError('Original populations, votes or assignment changed')
    if rebuilt.geometry.to_wkb().tolist()!=frame.geometry.to_wkb().tolist():raise ValueError('Geometry bytes changed')
    with warnings.catch_warnings(record=True):new_graph=Graph.from_geodataframe(rebuilt,adjacency='rook',cols_to_add=columns+[f'START_{s}' for s in args.seeds])
    signature=kernel_signature(frame,graph)
    if kernel_signature(rebuilt,new_graph)!=signature:raise ValueError('Sampler graph or population/vote kernel inputs changed')
    baseline_registry=json.loads(args.registry.read_text())
    experiment=copy.deepcopy(original);experiment.update(dataset=str(new_dataset.relative_to(ROOT)),dataset_sha256=file_sha256(new_dataset),
        seeds=args.seeds,steps=0,starting_plan='dispersed',prefix='tx_dispersed_20261102',
        input_dir=str((folder/'ensembles').relative_to(ROOT)),seed_configs={},starting_plan_hashes={},expected_checkpoint_provenance={},
        initialization_design='independent population-balanced recursive-tree starts' if args.independent_pool else 'population-weighted greedy maximin over original post-warmup checkpoints')
    (folder/'ensembles').mkdir();(folder/'checkpoints').mkdir()
    records=[]
    for seed,index in zip(args.seeds,selected):
        assignment=dict(enumerate(assignments[index].tolist()));pops={d:sum(int(frame.TOTPOP.iloc[i]) for i in frame.index if assignment[i]==d) for d in set(assignment.values())}
        deviation=max(abs(pop/(int(frame.TOTPOP.sum())/38)-1) for pop in pops.values())
        if len(pops)!=38 or deviation>original['epsilon']+1e-10:raise ValueError('Dispersed start violates population bounds')
        if any(not nx.is_connected(graph.subgraph([i for i in frame.index if assignment[i]==d])) for d in pops):raise ValueError('Dispersed district is disconnected')
        registry=copy.deepcopy(baseline_registry);state=registry['states']['texas'];plan=copy.deepcopy(state['plans']['current'])
        state['dataset']=experiment['dataset'];state['default_year']='dispersed';state['plans']={'dispersed':plan};registry['states']={'texas':state}
        state['notes']='Population-based dispersed starting assignments on the unchanged Texas graph, population and vote model.'
        plan.update(assignment=f'START_{seed}',state_label=experiment['prefix'],output_dir=experiment['input_dir'],checkpoint_dir=str((folder/'checkpoints').relative_to(ROOT)))
        plan['audit'].update(prefix=experiment['prefix'],seeds=args.seeds,output_dir=str((folder/'audit').relative_to(ROOT)))
        config=folder/f'seed_{seed}.json'
        with config.open('x') as stream:json.dump(registry,stream,indent=2);stream.write('\n')
        experiment['seed_configs'][str(seed)]=str(config.relative_to(ROOT));experiment['starting_plan_hashes'][str(seed)]=plan_hash(graph,assignment)
        profile=SimpleNamespace(dataset=new_dataset,state=experiment['prefix'],layer='precincts',assignment_col=f'START_{seed}',population_col='TOTPOP',dem_col='G24PREDHAR',rep_col='G24PRERTRU',epsilon=original['epsilon'],node_repeats=original['node_repeats'],sample_every=1)
        experiment['expected_checkpoint_provenance'][str(seed)]=provenance(profile,new_graph,ROOT/'src/chain/run_ensemble.py')
        records.append({'seed':seed,**candidates[index],'max_abs_population_deviation':deviation,'all_districts_graph_contiguous':True})
    experiment['config']=experiment['seed_configs'][str(args.seeds[0])]
    proof={'original_dataset_sha256':original['dataset_sha256'],'dispersed_dataset_sha256':experiment['dataset_sha256'],
           'kernel_signature_sha256':signature,'identical_geometry_bytes':True,'identical_original_unit_order_population_votes_and_assignment':True,
           'candidate_plans':len(candidates),'selection_anchor':candidates[anchor],'selection':'Population-weighted maximin ordering; election outcomes not used for selection',
           'starts':records,'source_geometry_warnings':[str(w.message) for w in captured]}
    with (folder/'kernel_equivalence.json').open('x') as stream:json.dump(proof,stream,indent=2);stream.write('\n')
    experiment['kernel_equivalence_file']=str((folder/'kernel_equivalence.json').relative_to(ROOT));experiment['kernel_equivalence_sha256']=file_sha256(folder/'kernel_equivalence.json')
    with (folder/'experiment.json').open('x') as stream:json.dump(experiment,stream,indent=2);stream.write('\n')
    print(json.dumps(proof,indent=2))


if __name__=='__main__':main()
