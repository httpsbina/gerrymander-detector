# Earlier Texas analysis

I reported these values for an earlier 30,000-state run; the [November 2026 source rebuild](../../deliverables/rebuild-campaign-2026-11-02/README.md) replaces this analysis. I keep the earlier tables and figures here as a historical record.

## Data and method

I used 9,712 geographic units, including 322 zero-population units, with population 29,145,505 and 38 congressional districts. The 2024 Harris-Trump presidential proxy totals were 4,835,134 and 6,393,403 votes. I aggregated Census-block population into the precinct geography and scored PLANC2333 using the block-level `C2333` assignments.

I sampled ReCom plans with graph contiguity and a +/-0.1% population bound. The retained run spans steps 700–30,699, with 30,000 states, 29,301 unique plans, and 699 duplicates. I reported a maximum population deviation of 0.099998%; warmup checks from 500 through 900 states gave similar averages, while first-half and second-half comparisons showed remaining drift.

## Reported map scores

| Map                              | Harris-majority districts | Efficiency gap | Mean-median | Maximum population deviation |
| -------------------------------- | ------------------------: | -------------: | ----------: | ---------------------------: |
| Earlier current map              |                        11 |      -0.130938 |   -0.057243 |                    0.052416% |
| Representative plan, step 26,999 |                        13 |      -0.049588 |   +0.008427 |                    0.098043% |
| PLANC2333 (2025)                 |                         8 |      -0.193900 |   -0.052861 |      approximately 0.000127% |

I reported a 9–17 seat range, a mean of 12.973, and a median of 13. The earlier current map's seat lower tail was 12.607%, its efficiency-gap lower tail was 0.517%, and its mean-median lower tail was 0.000% of observed states. I recorded zero retained states at or below the PLANC2333 score of 8.

I selected the representative plan from reconstructable median-seat states near the ensemble center on efficiency gap, mean-median, and cut edges. The earlier validation record reported complete assignments for all 38 districts in both the representative plan and PLANC2333, preserved statewide totals, and agreement between manual and GerryChain efficiency-gap and mean-median calculations.

## Recorded distribution

| Harris-won districts | Observed states |  Share |
| -------------------: | --------------: | -----: |
|                    9 |             116 |  0.39% |
|                   10 |             822 |  2.74% |
|                   11 |           2,844 |  9.48% |
|                   12 |           6,878 | 22.93% |
|                   13 |           8,721 | 29.07% |
|                   14 |           7,235 | 24.12% |
|                   15 |           2,732 |  9.11% |
|                   16 |             607 |  2.02% |
|                   17 |              45 |  0.15% |

The modal and median outcome is 13 Harris-won districts.

## Recorded effective sample sizes

| Metric         | Approximate ESS |
| -------------- | --------------: |
| Seat count     |              98 |
| Efficiency gap |              92 |
| Mean-median    |             118 |
| Cut edges      |             162 |

## Figures

![Historical seat distribution](../../outputs/figures/texas_dem_seat_distribution.png)

![Representative plan](../../outputs/figures/texas_representative_neutral_map.png)

![Earlier current map](../../outputs/figures/texas_current_map.png)

![PLANC2333](../../outputs/figures/texas_planc2333_map.png)

## Reproduction record

I used Python 3.12, GerryChain 0.3.2, GeoPandas, Pandas, NetworkX, SciPy, and Matplotlib. The recorded entry points were `src/chain/run_ensemble.py`, `src/analysis/analyze_texas_ensemble.py`, `src/analysis/analyze_thinning.py`, and `src/analysis/make_texas_final_figures.py`; the earlier precursor scripts remain under `src/legacy/`.

```powershell
$env:PYTHONHASHSEED = "0"
```

## Limitations

I no longer have the chain files for this earlier run, so these reported values have not been revalidated. The low ESS and remaining drift limit interpretation; the descriptive tails, including 0.000%, are neither calibrated p-values nor zero-probability claims. I used a presidential proxy and population/contiguity constraints, with no explicit county, municipality, compactness, Voting Rights Act, or communities-of-interest constraints. Uniform sampling and full legal compliance were not part of this model.

## References

DeFord, D., Duchin, M., and Solomon, J. (2021). [Recombination: A Family of Markov Chains for Redistricting](https://hdsr.mitpress.mit.edu/pub/1ds8ptxu). _Harvard Data Science Review_, 3(1).

Chikina, M., Frieze, A., and Pegden, W. (2017). [Assessing Significance in a Markov Chain without Mixing](https://www.pnas.org/doi/10.1073/pnas.1617540114). _PNAS_, 114(11).

Duchin, M. (2018). [Outlier Analysis for Pennsylvania Congressional Redistricting](https://mggg.org/uploads/md-report.pdf). Expert report, _League of Women Voters v. Commonwealth of Pennsylvania_.

Becker et al. (2021). [Computational Redistricting and the Voting Rights Act](https://www.brennancenter.org/sites/default/files/2023-11/Computational%20Redistricting%20and%20the%20Voting%20Rights%20Act%20FINAL%20PUBLISHED%20VERSION%20elj.2020.0704.pdf).
