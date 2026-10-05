# Gerrymander Detector

[![Python](https://img.shields.io/badge/Python-3.12-blue)](https://python.org)
[![GerryChain](https://img.shields.io/badge/GerryChain-0.3.2-green)](https://github.com/mggg/GerryChain)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)
[![Data](https://img.shields.io/badge/Data-Redistricting%20Data%20Hub-orange)](https://redistrictingdatahub.org)

Can we mathematically prove a congressional map is gerrymandered?

This project generates thousands of legally valid alternative district maps using [MCMC sampling](https://en.wikipedia.org/wiki/Markov_chain_Monte_Carlo) and checks whether the real enacted map is a statistical outlier. If the real map looks nothing like what a neutral process would produce, that's a red flag!

Built for my [PEAK Award](https://undergraduate.northeastern.edu/research/awards/peak-fellowships-overview/) research at [Northeastern University](https://www.northeastern.edu/). Texas is the proof of concept, the goal is to scale to every state.

---

## How it works

1. Pull precinct-level election and census data from the [Redistricting Data Hub](https://redistrictingdatahub.org) API
2. Build a dual graph where each precinct is a node and shared borders are edges
3. Run a Markov chain ([ReCom algorithm](https://mggg.org/samplers)) that randomly generates valid congressional maps with balanced population and contiguous districts
4. Collect metrics on each generated map (seats won, efficiency gap, mean-median difference)
5. Compare where the real enacted map falls in that distribution

If the enacted map sits outside the range of what random valid maps produce, it likely didn't come from a neutral process.

---

## Texas Results

Using 2024 presidential vote data across 9,712 validated precinct units and 30,000 post-burn-in ReCom states with a +/-0.1% population tolerance:

| Map | Dem Seats | Percentile | Outlier |
|-----|-----------|------------|---------|
| Current Texas map | 11 | 12.607% lower tail | Within seat range |
| PLANC2333 (2025) | 8 | **Below all observed states** | **Outlier** |
| Ensemble range | 9-17 | - | - |
| Ensemble mean | 12.973 | - | - |

No retained post-burn-in ensemble state produced as few as 8 Harris-won districts. The 2025 map, currently being challenged in [LULAC v. Abbott](https://www.democracydocket.com/cases/texas-redistricting-challenge-lulac/), sits completely outside the distribution.

### Ensemble Outlier Analysis

<p align="center">
  <img src="outputs/figures/texas_dem_seat_distribution.png" alt="Ensemble Analysis" width="800">
</p>

PLANC2333 lies below the observed 9 to 17 seat range. The current map produces 11 Harris-won districts and remains within the observed seat distribution.

### District Maps â€” 2021 vs 2025

<p align="center">
  <img src="outputs/figures/texas_representative_neutral_map.png" alt="District Maps" width="900">
</p>

The representative neutral plan is chain step 26,999. It has 13 Harris-won districts, efficiency gap -0.049588, mean-median +0.008427, and maximum population deviation 0.098043%.

---

## Why Texas

- **New maps.** One of the newest states to redraw district lines. Most existing gerrymandering projects haven't analyzed these maps yet.
- **Rare mid-decade redistricting.** States normally redraw every 10 years after the census. Texas redrew in 2025, [just 4 years after the last round](https://en.wikipedia.org/wiki/2025_Texas_redistricting).
- **Scale test.** 38 congressional districts makes it one of the largest and most complex states to redistrict. If the pipeline works here it works anywhere.

---

## Assumptions

- **Partisan proxy**: 2024 presidential race, following the approach in [Duchin's expert testimony](https://mggg.org/uploads/md-report.pdf) in the Pennsylvania redistricting case and the [MGGG Lab's](https://mggg.org) published work. Still just one election.
- **Constraints**: Population balance (Â±5%) and contiguity (every district is one connected piece). Does not enforce compactness or county preservation, which actually helps outlier findings since stricter rules would narrow the ensemble range further.
- **Data construction**: Census-block population is aggregated to the validated 2024 precinct geography. PLANC2333 is scored using exact block-level C2333 assignments rather than precinct centroids. The validated dataset contains 322 zero-population units and preserves the exact statewide population total.

---

## Project Structure

    src/
      data_prep/               data cleaning and merging
        build_texas_master.py
        build_texas_precincts.py
      chain/                   markov chain generation
        run_ensemble.py
      analysis/                outlier scoring and visualization
        analyze_texas_ensemble.py
        analyze_thinning.py
        make_texas_final_figures.py
      metrics/                 partisan and compactness metrics
    rdh_api_tool/              redistricting data hub api notebooks
    outputs/
      ensembles/               chain results (csv, not in repo)
      figures/                 plots and maps
    data/                      raw and processed shapefiles (not in repo)

---

## Stack

| Tool | Purpose |
|------|---------|
| [GerryChain](https://github.com/mggg/GerryChain) | MCMC redistricting sampling (ReCom algorithm) |
| [GeoPandas](https://geopandas.org) | Geospatial data wrangling |
| [NetworkX](https://networkx.org) | Graph construction and analysis |
| [Matplotlib](https://matplotlib.org) | Visualization |
| [Redistricting Data Hub](https://redistrictingdatahub.org) | Precinct-level election and boundary data |

---

## References

> DeFord, Duchin, & Solomon (2021). [Recombination: A Family of Markov Chains for Redistricting.](https://hdsr.mitpress.mit.edu/pub/1ds8ptxu) *Harvard Data Science Review*, 3(1).

> Chikina, Frieze, & Pegden (2017). [Assessing Significance in a Markov Chain without Mixing.](https://www.pnas.org/doi/10.1073/pnas.1617540114) *PNAS*, 114(11).

> Duchin (2018). [Outlier Analysis for Pennsylvania Congressional Redistricting.](https://mggg.org/uploads/md-report.pdf) Expert report, *League of Women Voters v. Commonwealth of Pennsylvania*.

> Becker et al. (2021). [Computational Redistricting and the Voting Rights Act.](https://www.brennancenter.org/sites/default/files/2023-11/Computational%20Redistricting%20and%20the%20Voting%20Rights%20Act%20FINAL%20PUBLISHED%20VERSION%20elj.2020.0704.pdf)

---

## Author

**Binafsha Bakhramova** â€” [Northeastern University](https://www.northeastern.edu/), D'Amore McKim School of Business

PEAK Award Research. Not affiliated with any political party, campaign, or advocacy organization.

Data sourced from the [Redistricting Data Hub](https://redistrictingdatahub.org).
