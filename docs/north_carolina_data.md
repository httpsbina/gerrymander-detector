# North Carolina Data Preparation

## Goal

Extend the Texas redistricting analysis pipeline to North Carolina
using Census population data, election results, and congressional
district assignments.

## Data needed

- 2020 Census block population
- 2024 presidential election results
- Congressional district assignments
- Precinct boundaries and geographic identifiers

## Validation

Before running simulations, check that:

1. Geographic identifiers match across datasets.
2. No Census blocks are lost during joins.
3. Population and election totals match the sources.
4. District assignments cover every geographic unit.
5. The initial district map is valid for GerryChain.

## Next steps

Build the North Carolina data preparation script, validate the
merged dataset, and run an initial ReCom test.
