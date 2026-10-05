"""
run_ensemble.py

Runs a reproducible ReCom Markov chain on a validated district dataset
2024 precinct dataset.

Important:
- Population comes from exact 2020 Census block aggregation.
- 2024 presidential votes come from block-disaggregated election data.
- Zero-population precincts remain zero.
- No graph components are dropped.
- The assignment column supplies the initial district map.
- PLANC2333 is scored separately at the block level and is NOT used to
  construct the neutral ensemble.

Example:
    python src/chain/run_ensemble.py --steps 500 --epsilon 0.01 --seed 101

epsilon examples:
    0.01  = +/- 1.0%
    0.005 = +/- 0.5%
    0.001 = +/- 0.1%
"""

import argparse
import hashlib
import os
import random
import pickle

import geopandas as gpd
import networkx as nx
import pandas as pd

from functools import partial

from gerrychain import (
    Graph,
    GeographicPartition,
    MarkovChain,
    Election,
)

from gerrychain.proposals import recom
from gerrychain.updaters import Tally, cut_edges

from gerrychain.constraints import (
    within_percent_of_ideal_population,
    contiguous,
)

from gerrychain.accept import always_accept

from gerrychain.tree import bipartition_tree

ROOT = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
    )
)

DEFAULT_OUTPUT_DIR = os.path.join(
    ROOT,
    "outputs",
    "ensembles",
)

DEFAULT_CHECKPOINT_DIR = os.path.join(
    ROOT,
    "outputs",
    "checkpoints",
)

def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Run a reproducible ReCom ensemble from a validated "
            "district dataset."
        )
    )

    parser.add_argument(
        "--state",
        type=str,
        required=True,
        help=(
            "State or jurisdiction name used for labels "
            "and output filenames."
        ),
    )

    parser.add_argument(
        "--dataset",
        type=str,
        required=True,
        help="Path to the validated GeoPackage or shapefile.",
    )

    parser.add_argument(
        "--layer",
        type=str,
        default="precincts",
        help="Layer name when reading a GeoPackage.",
    )

    parser.add_argument(
        "--assignment-col",
        type=str,
        required=True,
        help="Column containing the initial district assignment.",
    )

    parser.add_argument(
        "--population-col",
        type=str,
        required=True,
        help="Population column used for ReCom balancing.",
    )

    parser.add_argument(
        "--dem-col",
        type=str,
        required=True,
        help="Democratic vote column.",
    )

    parser.add_argument(
        "--rep-col",
        type=str,
        required=True,
        help="Republican vote column.",
    )

    parser.add_argument(
        "--output-dir",
        type=str,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for ensemble CSV outputs.",
    )

    parser.add_argument(
        "--checkpoint-dir",
        type=str,
        default=DEFAULT_CHECKPOINT_DIR,
        help="Directory for chain checkpoints.",
    )

    parser.add_argument(
        "--steps",
        type=int,
        default=500,
        help="Total Markov chain states including the initial state.",
    )

    parser.add_argument(
        "--epsilon",
        type=float,
        default=0.01,
        help=(
            "Allowed population deviation. "
            "0.01 = 1%%, 0.005 = 0.5%%, "
            "0.001 = 0.1%%."
        ),
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=101,
        help="Random seed for reproducibility.",
    )

    parser.add_argument(
        "--sample-every",
        type=int,
        default=1,
        help="Record every Nth state.",
    )

    parser.add_argument(
        "--node-repeats",
        type=int,
        default=2,
        help="ReCom node_repeats parameter.",
    )

    parser.add_argument(
        "--resume-from",
        type=str,
        default=None,
        help="Resume from a saved GerryChain checkpoint.",
    )

    return parser.parse_args()

def plan_hash(partition):
    """
    Label-independent exact plan fingerprint.

    A plan is represented by its sorted set of cut edges.
    Full SHA-256 is retained so fingerprints are consistent
    across validation scripts.
    """

    edges = []

    for u, v in partition["cut_edges"]:
        a, b = sorted(
            (
                str(u),
                str(v),
            )
        )

        edges.append(
            (a, b)
        )

    edges = sorted(edges)

    payload = "|".join(
        f"{u}:{v}"
        for u, v in edges
    )

    return hashlib.sha256(
        payload.encode("utf-8")
    ).hexdigest()

def population_stats(partition, ideal_pop):
    pops = list(
        partition["population"].values()
    )

    deviations = [
        abs(pop / ideal_pop - 1)
        for pop in pops
    ]

    return {
        "min_pop": min(pops),
        "max_pop": max(pops),
        "max_abs_pop_dev": max(deviations),
    }

def dem_seats(partition):
    return sum(
        1
        for pct in partition[
            "ELECTION"
        ].percents("Dem")
        if pct > 0.5
    )

args = parse_args()

if args.steps < 1:
    raise ValueError(
        "--steps must be at least 1"
    )

if args.epsilon <= 0:
    raise ValueError(
        "--epsilon must be positive"
    )

if args.sample_every < 1:
    raise ValueError(
        "--sample-every must be at least 1"
    )


state_label = args.state.strip()

state_slug = (
    state_label
    .lower()
    .replace(" ", "_")
)

dataset_path = os.path.abspath(
    args.dataset
)

output_dir = os.path.abspath(
    args.output_dir
)

checkpoint_dir = os.path.abspath(
    args.checkpoint_dir
)


if not os.path.exists(dataset_path):
    raise FileNotFoundError(
        f"Dataset not found: {dataset_path}"
    )


print(f"{state_label} validated ensemble")
print("=" * (len(state_label) + 19))

print(
    f"steps:        {args.steps:,}"
)

print(
    f"epsilon:      {args.epsilon:.6f} "
    f"({args.epsilon:.3%})"
)

print(
    f"random seed:  {args.seed}"
)

print(
    f"sample every: {args.sample_every}"
)

print(
    f"node repeats: {args.node_repeats}"
)


print("\nloading validated district dataset...")


if dataset_path.lower().endswith(".gpkg"):
    gdf = gpd.read_file(
        dataset_path,
        layer=args.layer,
    )
else:
    gdf = gpd.read_file(
        dataset_path
    )


required_columns = [
    args.assignment_col,
    args.population_col,
    args.dem_col,
    args.rep_col,
]


missing_columns = [
    column
    for column in required_columns
    if column not in gdf.columns
]


if missing_columns:
    raise ValueError(
        "Dataset is missing required columns: "
        + ", ".join(missing_columns)
    )


for column in required_columns:
    if gdf[column].isna().any():
        raise ValueError(
            f"Column contains missing values: {column}"
        )

num_units = len(gdf)

total_pop = int(
    gdf[args.population_col].sum()
)

total_dem = int(
    gdf[args.dem_col].sum()
)

total_rep = int(
    gdf[args.rep_col].sum()
)

num_districts = int(
    gdf[args.assignment_col].nunique()
)


print(
    f"  geographic units: {num_units:,}"
)

print(
    f"  districts:        {num_districts:,}"
)

print(
    f"  population:       {total_pop:,}"
)

print(
    f"  Dem votes:        {total_dem:,}"
)

print(
    f"  Rep votes:        {total_rep:,}"
)

print(
    f"  zero-pop units:   "
    f"{(gdf[args.population_col] == 0).sum():,}"
)


print("\nbuilding adjacency graph...")


graph = Graph.from_geodataframe(
    gdf,
    cols_to_add=required_columns,
)


if len(graph.nodes) != num_units:
    raise RuntimeError(
        "Graph node count does not match "
        "the input dataset."
    )


components = list(
    nx.connected_components(graph)
)

isolates = list(
    nx.isolates(graph)
)


print(
    f"  nodes: {len(graph.nodes):,}"
)

print(
    f"  edges: {len(graph.edges):,}"
)

print(
    f"  connected components: "
    f"{len(components)}"
)

print(
    f"  isolates: {len(isolates)}"
)


if len(components) != 1:
    raise RuntimeError(
        f"{state_label} adjacency graph is not connected. "
        "No components will be silently dropped."
    )


if isolates:
    raise RuntimeError(
        f"{state_label} adjacency graph contains "
        "isolated nodes."
    )

print("\nchecking graph totals...")

graph_pop = sum(
    int(graph.nodes[node][args.population_col])
    for node in graph.nodes
)

graph_dem = sum(
    int(graph.nodes[node][args.dem_col])
    for node in graph.nodes
)

graph_rep = sum(
    int(graph.nodes[node][args.rep_col])
    for node in graph.nodes
)

if graph_pop != total_pop:
    raise RuntimeError(
        "Graph population total does not match dataset."
    )

if graph_dem != total_dem:
    raise RuntimeError(
        "Graph Democratic vote total does not match dataset."
    )

if graph_rep != total_rep:
    raise RuntimeError(
        "Graph Republican vote total does not match dataset."
    )

print(
    f"  population: {graph_pop:,}"
)

print(
    f"  Dem votes:  {graph_dem:,}"
)

print(
    f"  Rep votes:  {graph_rep:,}"
)


election = Election(
    "ELECTION",
    {
        "Dem": args.dem_col,
        "Rep": args.rep_col,
    },
)


updaters = {
    "population": Tally(
        args.population_col,
        alias="population",
    ),
    "cut_edges": cut_edges,
    "ELECTION": election,
}

updaters = {
    "population": Tally(
        args.population_col,
        alias="population",
    ),
    "cut_edges": cut_edges,
    "ELECTION": election,
}


resume_checkpoint = None
start_step = 0
run_seed = args.seed


if args.resume_from:
    print("\nloading checkpoint...")

    with open(args.resume_from, "rb") as f:
        resume_checkpoint = pickle.load(f)

    assignment = resume_checkpoint["assignment"]

    if set(assignment.keys()) != set(graph.nodes):
        raise RuntimeError(
            "Checkpoint nodes do not match current graph."
        )

    initial = GeographicPartition(
        graph,
        assignment=assignment,
        updaters=updaters,
    )

    start_step = int(
        resume_checkpoint["next_step"]
    )

    run_seed = int(
        resume_checkpoint["seed"]
    )

    saved_hash_seed = resume_checkpoint.get(
        "pythonhashseed"
    )

    current_hash_seed = os.environ.get(
        "PYTHONHASHSEED"
    )

    if saved_hash_seed != current_hash_seed:
        raise RuntimeError(
            "PYTHONHASHSEED does not match checkpoint. "
            f"Checkpoint={saved_hash_seed}, "
            f"current={current_hash_seed}"
        )

    random.setstate(
        resume_checkpoint["random_state"]
    )

    print(
        f"  resuming at step: {start_step:,}"
    )

    print(
        f"  original seed:    {run_seed}"
    )

else:
    initial = GeographicPartition(
        graph,
        assignment=args.assignment_col,
        updaters=updaters,
    )

    random.seed(args.seed)


initial_num_districts = len(initial)

if initial_num_districts != num_districts:
    raise RuntimeError(
        "Initial partition district count does not match "
        "the dataset district count."
    )


partition_total_pop = sum(
    initial["population"].values()
)

if partition_total_pop != total_pop:
    raise RuntimeError(
        "Initial partition population does not match "
        "the dataset population."
    )


ideal_pop = (
    partition_total_pop
    / initial_num_districts
)

num_districts = initial_num_districts

initial_pop_stats = population_stats(
    initial,
    ideal_pop,
)

initial_dem_seats = dem_seats(
    initial
)

initial_hash = plan_hash(
    initial
)


print("\ninitial seed map:")

print(
    f"  districts: "
    f"{num_districts}"
)

print(
    f"  ideal population: "
    f"{ideal_pop:,.6f}"
)

print(
    f"  population range: "
    f"{initial_pop_stats['min_pop']:,} - "
    f"{initial_pop_stats['max_pop']:,}"
)

print(
    f"  max population deviation: "
    f"{initial_pop_stats['max_abs_pop_dev']:.6%}"
)

print(
    f"  Dem > Rep districts: "
    f"{initial_dem_seats}/{num_districts}"
)

print(
    f"  efficiency gap: "
    f"{initial['ELECTION'].efficiency_gap():.6f}"
)

print(
    f"  mean-median: "
    f"{initial['ELECTION'].mean_median():.6f}"
)

print(
    f"  cut edges: "
    f"{len(initial['cut_edges']):,}"
)

print(
    f"  plan hash: "
    f"{initial_hash}"
)


if (
    initial_pop_stats[
        "max_abs_pop_dev"
    ]
    > args.epsilon
):
    raise RuntimeError(
        "Initial seed map exceeds requested "
        f"epsilon ({args.epsilon:.6%}). "
        "Use a larger epsilon or construct "
        "a different seed plan."
    )

proposal = partial(
    recom,
    pop_col=args.population_col,
    pop_target=ideal_pop,
    epsilon=args.epsilon,
    node_repeats=args.node_repeats,
    method=partial(
        bipartition_tree,
        max_attempts=1000,
        allow_pair_reselection=True,
    ),
)


constraints = [
    within_percent_of_ideal_population(
        initial,
        args.epsilon,
    ),
    contiguous,
]


chain_total_steps = (
    args.steps + 1
    if args.resume_from
    else args.steps
)

chain = MarkovChain(
    proposal=proposal,
    constraints=constraints,
    accept=always_accept,
    initial_state=initial,
    total_steps=chain_total_steps,
)

def save_checkpoint(partition, next_step):
    os.makedirs(
        checkpoint_dir,
        exist_ok=True,
    )

    checkpoint = {
        "version": 1,
        "seed": run_seed,
        "epsilon": args.epsilon,
        "node_repeats": args.node_repeats,
        "next_step": next_step,
        "assignment": dict(
            partition.assignment
        ),
        "random_state": random.getstate(),
        "pythonhashseed": os.environ.get(
            "PYTHONHASHSEED"
        ),
    }

    eps_tag = (
        f"{args.epsilon:g}"
        .replace(".", "p")
    )

    checkpoint_path = os.path.join(
        checkpoint_dir,
        (
            f"{state_slug}_checkpoint_"
            f"eps{eps_tag}_"
            f"seed{run_seed}_"
            f"next{next_step}.pkl"
        ),
    )

    with open(checkpoint_path, "wb") as f:
        pickle.dump(
            checkpoint,
            f,
            protocol=pickle.HIGHEST_PROTOCOL,
        )

    return checkpoint_path

print("\nrunning chain...")

results = []


try:

    recorded = 0
    final_partition = None

    for local_step, partition in enumerate(
        chain
    ):

        # When resuming, GerryChain first yields
        # the checkpoint map itself. That state was
        # already recorded in the previous run.
        if (
            args.resume_from
            and local_step == 0
        ):
            continue

        step = (
            start_step
            + recorded
        )

        recorded += 1
        periodic_next_step = (
            start_step
            + recorded
        )

        if periodic_next_step % 100 == 0:
            periodic_checkpoint = save_checkpoint(
                partition,
                periodic_next_step,
            )

            print(
                f"  periodic checkpoint: "
                f"next step "
                f"{periodic_next_step:,}"
            )
    
        if (
            step
            % args.sample_every
            == 0
        ):

            pop_stats = population_stats(
                partition,
                ideal_pop,
            )

            results.append(
                {
                    "seed": run_seed,
                    "epsilon": args.epsilon,
                    "step": step,
                    "dem_seats": dem_seats(
                        partition
                    ),
                    "cut_edges": len(
                        partition[
                            "cut_edges"
                        ]
                    ),
                    "efficiency_gap": (
                        partition[
                            "ELECTION"
                        ].efficiency_gap()
                    ),
                    "mean_median": (
                        partition[
                            "ELECTION"
                        ].mean_median()
                    ),
                    "min_pop": (
                        pop_stats[
                            "min_pop"
                        ]
                    ),
                    "max_pop": (
                        pop_stats[
                            "max_pop"
                        ]
                    ),
                    "max_abs_pop_dev": (
                        pop_stats[
                            "max_abs_pop_dev"
                        ]
                    ),
                    "plan_hash": (
                        plan_hash(
                            partition
                        )
                    ),
                }
            )

        if (
            recorded == 1
            or recorded % 100 == 0
            or recorded == args.steps
        ):
            print(
                f"  global step "
                f"{step:,} "
                f"(new "
                f"{recorded:,}/"
                f"{args.steps:,})"
            )

except RuntimeError as exc:

    print()
    print(
        "CHAIN STOPPED WITH RuntimeError"
    )

    print(
        str(exc)
    )

    print(
        "\nThis may indicate that the "
        "requested population tolerance "
        "is difficult for ReCom to satisfy."
    )

    raise

next_step = (
    start_step
    + recorded
)

checkpoint_path = save_checkpoint(
    partition,
    next_step,
)

print("\ncheckpoint saved:")
print(
    f"  {checkpoint_path}"
)

print(
    f"  next run begins at "
    f"step {next_step:,}"
)

df = pd.DataFrame(
    results
)


if df.empty:
    raise RuntimeError(
        "No chain samples were recorded."
    )


os.makedirs(
    output_dir,
    exist_ok=True,
)


epsilon_tag = (
    f"{args.epsilon:.4f}"
    .rstrip("0")
    .rstrip(".")
    .replace(".", "p")
)

output_name = (
    f"{state_slug}_chain_"
    f"eps{epsilon_tag}_"
    f"seed{args.seed}_"
    f"{args.steps}steps.csv"
)

end_step = (
    start_step
    + recorded
    - 1
)

output_path = os.path.join(
    output_dir,
    (
        f"{state_slug}_chain_"
        f"eps{epsilon_tag}_"        
        f"seed{run_seed}_"
        f"steps{start_step:06d}-"
        f"{end_step:06d}.csv"
    ),
)

df.to_csv(
    output_path,
    index=False,
)


unique_plans = (
    df["plan_hash"].nunique()
)

duplicate_states = (
    len(df)
    - unique_plans
)


print("\nchain complete")
print("==============")

print(
    f"recorded states: "
    f"{len(df):,}"
)

print(
    f"unique exact plans: "
    f"{unique_plans:,}"
)

print(
    f"duplicate states: "
    f"{duplicate_states:,}"
)

print(
    f"Dem-seat range: "
    f"{df['dem_seats'].min()} - "
    f"{df['dem_seats'].max()}"
)

print(
    f"mean Dem seats: "
    f"{df['dem_seats'].mean():.3f}"
)

print(
    f"max observed population deviation: "
    f"{df['max_abs_pop_dev'].max():.6%}"
)

print(
    f"saved to:"
)

print(
    f"  {output_path}"
)

print("\ndone!")






