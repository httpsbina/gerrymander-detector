# North Carolina Congressional Redistricting Research

## Objective

Compare North Carolina's 2023 and 2025 enacted
congressional maps using a common geographic dataset,
modeled 2024 presidential votes, and ReCom simulations.

## Data

- 2,681 common geographic units
- 7,583 adjacency edges
- 14 congressional districts
- 2020 Census population: 10,439,388
- Modeled Harris votes: 2,713,609
- Modeled Trump votes: 2,896,942

The 2024 presidential vote allocations are modeled
at the Census-block level, not directly observed
individual block election results.

Both enacted maps produce 3 Harris-won districts
under this election model.

## Ensemble construction

Six independent ReCom chains were initialized using
the two enacted congressional assignments.

Starting maps: 2023 and 2025
Seeds: 707, 808, 909
States per chain: 5,000
Total recorded states: 30,000
Population tolerance: +/-0.5%
ReCom node_repeats: 2

Both groups use the same underlying geographic graph.

The initial enacted map is not a distinct target
distribution. These chains are intended to explore
the same ReCom process from different initial maps.

ReCom does not uniformly sample all valid plans.

## Convergence diagnostics

After discarding the first 500 states per chain:

Retained states: 27,000

Combined six-chain diagnostics:

- Democratic seats: Rhat 1.0349; bulk ESS 199.3
- Efficiency gap: Rhat 1.0367; bulk ESS 202.0
- Cut edges: Rhat 1.0103; bulk ESS 494.1

The chains exhibit substantial autocorrelation
and differences between sampling trajectories.

Alternative warm-up periods of 2,000 and 3,000
states did not consistently resolve these problems.

Convergence has not been established.

Rare seat-outcome counts must not be interpreted
as calibrated probabilities or gerrymandering
p-values.

## Population-equality sensitivity

Two 100-state feasibility pilots were completed
with the stricter +/-0.1% population tolerance.

2023 start:
- 100 recorded states
- 99 unique exact plans
- Maximum deviation: 0.099297%

2025 start:
- 100 recorded states
- 98 unique exact plans
- Maximum deviation: 0.099853%

These tests establish technical feasibility only.
They do not establish convergence at +/-0.1%.

## Election vote-swing sensitivity

The enacted maps were evaluated under hypothetical
uniform shifts of -3 to +3 percentage points in
district-level Harris two-party vote share.

The 2023 enacted map increases from 3 to 4
Harris-won districts at +2 percentage points.
District 1 changes winner.

The 2025 enacted map remains at 3 Harris-won
districts through +3 percentage points.

This test is not equivalent to using independently
observed block-level votes or another election year.

## Limitations

1. Ensemble convergence remains unresolved.
2. Consecutive ReCom states are correlated.
3. The sampler is not uniform over all valid maps.
4. The implemented constraints do not independently
   establish compliance with every applicable legal
   redistricting requirement.
5. The election data include modeled allocations.
6. Uniform vote swings do not replace independent
   election-data sensitivity analysis.
7. The stricter population pilot has only 100 states
   per starting map.

No precise outlier probability or causal estimate
is supported by the existing simulations.

## Reproduction

Run from the repository root after installing the
project environment and preparing the local data:

python src/analysis/analyze_nc_common_chains.py
python src/analysis/analyze_nc_vote_sensitivity.py
python src/analysis/make_nc_figures.py

Generated CSVs and PNG figures are written under
outputs/analysis/.

These outputs, raw data, processed data, and simulation
checkpoints are excluded from regular Git commits.

The scripts reproduce the descriptive analysis without
rerunning the existing ReCom chains.

## Research status

The planned initial simulations and sensitivity pilots
are complete.

The study is reproducible as a descriptive case study.
Further inferential claims require stronger convergence
evidence and additional methodological validation.
