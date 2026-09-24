"""
test_texas_map_diversity.py

Separate validation experiment for the Texas GerryChain ensemble.

Questions:
1. Are generated plans exact duplicates?
2. How different are generated plans from the seed map?
3. How much does each consecutive plan actually change?

Similarity is label-independent. District labels are optimally matched
using population overlap before calculating the share of Texas
population assigned equivalently.

This is a validation test, not the production ensemble generator.
"""

import argparse
import hashlib
import os
import random
from functools import partial

import geopandas as gpd
import networkx as nx
import numpy as np
import pandas as pd

from scipy.optimize import linear_sum_assignment

from gerrychain import (
    Election,
    GeographicPartition,
    Graph,
    MarkovChain,
)

from gerrychain.accept import always_accept
from gerrychain.constraints import (
    contiguous,
    within_percent_of_ideal_population,
)
from gerrychain.proposals import recom
from gerrychain.updaters import Tally, cut_edges


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
    "validation",
)

EXPECTED_PRECINCTS = 9_712
EXPECTED_POP = 29_145_505
EXPECTED_DISTRICTS = 38


def parse_args():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--steps",
        type=int,
        default=100,
    )

    parser.add_argument(
        "--epsilon",
        type=float,
        default=0.001,
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=101,
    )

    return parser.parse_args()


def canonical_cut_edges(partition):
    edges = []

    for u, v in partition["cut_edges"]:
        a, b = sorted((str(u), str(v)))
        edges.append((a, b))

    return tuple(sorted(edges))


def exact_plan_hash(partition):
    edges = canonical_cut_edges(partition)

    payload = "|".join(
        f"{u}:{v}"
        for u, v in edges
    )

    return hashlib.sha256(
        payload.encode("utf-8")
    ).hexdigest()


def assignment_array(partition, node_order):
    return np.array(
        [
            str(partition.assignment[node])
            for node in node_order
        ],
        dtype=object,
    )


def population_similarity(
    assignment_a,
    assignment_b,
    populations,
):
    """
    Label-independent similarity.

    Creates a 38x38 population-overlap matrix between two plans,
    optimally matches districts, then calculates the fraction of
    statewide population placed into corresponding districts.
    """

    labels_a = sorted(
        np.unique(assignment_a)
    )

    labels_b = sorted(
        np.unique(assignment_b)
    )

    if (
        len(labels_a) != EXPECTED_DISTRICTS
        or len(labels_b) != EXPECTED_DISTRICTS
    ):
        raise ValueError(
            "Unexpected number of districts."
        )

    index_a = {
        label: i
        for i, label in enumerate(labels_a)
    }

    index_b = {
        label: i
        for i, label in enumerate(labels_b)
    }

    overlap = np.zeros(
        (
            EXPECTED_DISTRICTS,
            EXPECTED_DISTRICTS,
        ),
        dtype=np.int64,
    )

    for a, b, pop in zip(
        assignment_a,
        assignment_b,
        populations,
    ):
        overlap[
            index_a[a],
            index_b[b],
        ] += int(pop)

    rows, cols = linear_sum_assignment(
        -overlap
    )

    matched_population = overlap[
        rows,
        cols,
    ].sum()

    return (
        matched_population
        / populations.sum()
    )


args = parse_args()

print("Texas map-diversity validation")
print("==============================")
print(f"steps:   {args.steps}")
print(f"epsilon: {args.epsilon:.3%}")
print(f"seed:    {args.seed}")


print("\nloading dataset...")

gdf = gpd.read_file(
    DATASET_PATH,
    layer="precincts",
)

assert len(gdf) == EXPECTED_PRECINCTS
assert gdf["TOTPOP"].sum() == EXPECTED_POP


print("building graph...")

graph = Graph.from_file(
    DATASET_PATH
)

assert nx.is_connected(graph)


election = Election(
    "PRES24",
    {
        "Dem": "G24PREDHAR",
        "Rep": "G24PRERTRU",
    },
)


initial = GeographicPartition(
    graph,
    assignment="CONG_DIST",
    updaters={
        "population": Tally(
            "TOTPOP",
            alias="population",
        ),
        "cut_edges": cut_edges,
        "PRES24": election,
    },
)


ideal_pop = (
    EXPECTED_POP
    / EXPECTED_DISTRICTS
)


random.seed(args.seed)


proposal = partial(
    recom,
    pop_col="TOTPOP",
    pop_target=ideal_pop,
    epsilon=args.epsilon,
    node_repeats=2,
)


constraints = [
    within_percent_of_ideal_population(
        initial,
        args.epsilon,
    ),
    contiguous,
]


chain = MarkovChain(
    proposal=proposal,
    constraints=constraints,
    accept=always_accept,
    initial_state=initial,
    total_steps=args.steps,
)


node_order = sorted(
    graph.nodes
)

populations = np.array(
    [
        int(
            graph.nodes[node]["TOTPOP"]
        )
        for node in node_order
    ],
    dtype=np.int64,
)

assert populations.sum() == EXPECTED_POP


seed_assignment = assignment_array(
    initial,
    node_order,
)

seed_hash = exact_plan_hash(
    initial
)


seen_hashes = set()
previous_assignment = None

results = []


print("\nrunning diversity test...")

for step, partition in enumerate(chain):

    current_assignment = assignment_array(
        partition,
        node_order,
    )

    current_hash = exact_plan_hash(
        partition
    )

    exact_duplicate = (
        current_hash in seen_hashes
    )

    seen_hashes.add(
        current_hash
    )

    seed_similarity = population_similarity(
        seed_assignment,
        current_assignment,
        populations,
    )

    if previous_assignment is None:
        previous_similarity = 1.0
    else:
        previous_similarity = population_similarity(
            previous_assignment,
            current_assignment,
            populations,
        )

    changed_from_seed = (
        1.0 - seed_similarity
    )

    changed_from_previous = (
        1.0 - previous_similarity
    )

    results.append(
        {
            "step": step,
            "plan_hash": current_hash,
            "exact_duplicate": exact_duplicate,
            "similarity_to_seed": seed_similarity,
            "changed_from_seed": changed_from_seed,
            "similarity_to_previous": previous_similarity,
            "changed_from_previous": changed_from_previous,
            "cut_edges": len(
                partition["cut_edges"]
            ),
        }
    )

    previous_assignment = (
        current_assignment.copy()
    )

    if (
        step % 25 == 0
        or step == args.steps - 1
    ):
        print(
            f"  step {step}/{args.steps - 1}"
        )


df = pd.DataFrame(results)

duplicates = int(
    df["exact_duplicate"].sum()
)

unique_plans = int(
    df["plan_hash"].nunique()
)


print("\nresults")
print("=======")

print(
    f"states generated:     {len(df):,}"
)

print(
    f"unique exact plans:   {unique_plans:,}"
)

print(
    f"exact duplicates:     {duplicates:,}"
)

print(
    f"seed hash:            {seed_hash}"
)

print()

print(
    "similarity to original seed map:"
)

print(
    f"  minimum: "
    f"{df['similarity_to_seed'].min():.4%}"
)

print(
    f"  mean:    "
    f"{df['similarity_to_seed'].mean():.4%}"
)

print(
    f"  final:   "
    f"{df['similarity_to_seed'].iloc[-1]:.4%}"
)

print()

print(
    "population changed vs seed:"
)

print(
    f"  maximum: "
    f"{df['changed_from_seed'].max():.4%}"
)

print(
    f"  final:   "
    f"{df['changed_from_seed'].iloc[-1]:.4%}"
)

print()

print(
    "consecutive-map similarity:"
)

print(
    f"  minimum: "
    f"{df['similarity_to_previous'].min():.4%}"
)

print(
    f"  mean:    "
    f"{df['similarity_to_previous'].mean():.4%}"
)

print()

print(
    "population changed per ReCom step:"
)

print(
    f"  maximum: "
    f"{df['changed_from_previous'].max():.4%}"
)

print(
    f"  mean:    "
    f"{df['changed_from_previous'].mean():.4%}"
)


os.makedirs(
    OUTPUT_DIR,
    exist_ok=True,
)

output_path = os.path.join(
    OUTPUT_DIR,
    (
        f"tx_map_diversity_"
        f"eps{args.epsilon}_"
        f"seed{args.seed}_"
        f"{args.steps}steps.csv"
    ),
)

df.to_csv(
    output_path,
    index=False,
)


print("\nsaved:")
print(f"  {output_path}")

print("\ndone!")