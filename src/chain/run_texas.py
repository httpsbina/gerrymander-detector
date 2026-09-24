"""
run_texas.py

Runs a reproducible ReCom Markov chain on the validated Texas
2024 precinct dataset.

Important:
- Population comes from exact 2020 Census block aggregation.
- 2024 presidential votes come from block-disaggregated election data.
- Zero-population precincts remain zero.
- No graph components are dropped.
- CONG_DIST is the 2024 congressional map used only as the initial seed.
- PLANC2333 is scored separately at the block level and is NOT used to
  construct the neutral ensemble.

Example:
    python src/chain/run_texas.py --steps 500 --epsilon 0.01 --seed 101

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


ROOT = os.path.join(
    os.path.expanduser("~"),
    "OneDrive",
    "Documents",
    "gerrymander-detector",
)

DATASET_PATH = os.path.join(
    ROOT,
    "data",
    "processed",
    "tx_precincts_validated.gpkg",
)

OUTPUT_DIR = os.path.join(
    ROOT,
    "outputs",
    "ensembles",
)

CHECKPOINT_DIR = os.path.join(
    ROOT,
    "outputs",
    "checkpoints",
)

EXPECTED_PRECINCTS = 9_712
EXPECTED_POP = 29_145_505
EXPECTED_HARRIS = 4_835_134
EXPECTED_TRUMP = 6_393_403
EXPECTED_DISTRICTS = 38


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Run a validated Texas ReCom ensemble."
        )
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
            "PRES24"
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


print("Texas validated ensemble")
print("========================")

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


print("\nloading validated precinct dataset...")

gdf = gpd.read_file(
    DATASET_PATH,
    layer="precincts",
)

assert len(gdf) == EXPECTED_PRECINCTS
assert gdf["TOTPOP"].sum() == EXPECTED_POP
assert gdf["G24PREDHAR"].sum() == EXPECTED_HARRIS
assert gdf["G24PRERTRU"].sum() == EXPECTED_TRUMP
assert gdf["CONG_DIST"].nunique() == EXPECTED_DISTRICTS

print(
    f"  precincts: {len(gdf):,}"
)

print(
    f"  population: {gdf['TOTPOP'].sum():,}"
)

print(
    f"  zero-pop precincts: "
    f"{(gdf['TOTPOP'] == 0).sum():,}"
)


print("\nbuilding adjacency graph...")

graph = Graph.from_file(
    DATASET_PATH
)

assert len(graph.nodes) == EXPECTED_PRECINCTS

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
        "Texas precinct graph is not connected. "
        "No components will be silently dropped."
    )

if isolates:
    raise RuntimeError(
        "Texas precinct graph contains isolated nodes."
    )


print("\nchecking graph totals...")

graph_pop = sum(
    int(graph.nodes[node]["TOTPOP"])
    for node in graph.nodes
)

graph_harris = sum(
    int(graph.nodes[node]["G24PREDHAR"])
    for node in graph.nodes
)

graph_trump = sum(
    int(graph.nodes[node]["G24PRERTRU"])
    for node in graph.nodes
)

assert graph_pop == EXPECTED_POP
assert graph_harris == EXPECTED_HARRIS
assert graph_trump == EXPECTED_TRUMP

print(
    f"  population: {graph_pop:,}"
)

print(
    f"  Harris: {graph_harris:,}"
)

print(
    f"  Trump: {graph_trump:,}"
)


election = Election(
    "PRES24",
    {
        "Dem": "G24PREDHAR",
        "Rep": "G24PRERTRU",
    },
)


updaters = {
    "population": Tally(
        "TOTPOP",
        alias="population",
    ),
    "cut_edges": cut_edges,
    "PRES24": election,
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
        assignment="CONG_DIST",
        updaters=updaters,
    )

    random.seed(args.seed)

num_districts = len(initial)

assert (
    num_districts
    == EXPECTED_DISTRICTS
)

total_pop = sum(
    initial["population"].values()
)

ideal_pop = (
    total_pop
    / num_districts
)

assert total_pop == EXPECTED_POP


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
    f"  Harris > Trump districts: "
    f"{initial_dem_seats}/{num_districts}"
)

print(
    f"  efficiency gap: "
    f"{initial['PRES24'].efficiency_gap():.6f}"
)

print(
    f"  mean-median: "
    f"{initial['PRES24'].mean_median():.6f}"
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
    pop_col="TOTPOP",
    pop_target=ideal_pop,
    epsilon=args.epsilon,
    node_repeats=args.node_repeats,
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

        final_partition = partition

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
                            "PRES24"
                        ].efficiency_gap()
                    ),
                    "mean_median": (
                        partition[
                            "PRES24"
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

if final_partition is None:
    raise RuntimeError(
        "No final partition available "
        "for checkpoint."
    )


os.makedirs(
    CHECKPOINT_DIR,
    exist_ok=True,
)


next_step = (
    start_step
    + recorded
)


checkpoint = {
    "version": 1,
    "seed": run_seed,
    "epsilon": args.epsilon,
    "node_repeats": args.node_repeats,
    "next_step": next_step,
    "assignment": dict(
        final_partition.assignment
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
    CHECKPOINT_DIR,
    (
        f"tx_checkpoint_"
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
    OUTPUT_DIR,
    exist_ok=True,
)


epsilon_tag = (
    f"{args.epsilon:.4f}"
    .rstrip("0")
    .rstrip(".")
    .replace(".", "p")
)

output_name = (
    f"tx_chain_"
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
    OUTPUT_DIR,
    (
        f"tx_chain_"
        f"eps{eps_tag}_"
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