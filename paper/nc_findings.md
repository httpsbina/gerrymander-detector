# North Carolina findings

- I ran 6 chains, recording 138,000 states and retaining 135,000 after warmup.
- I recorded 23,000 states per chain and used 500 warmup states, leaving 22,500 per chain.
- I started nc_block_union_2023 from the 2023 assignment with seeds 707, 808, 909; its initial map has 3 Democratic-majority districts under the presidential vote model.
- I started nc_block_union_2025 from the 2025 assignment with seeds 1707, 1808, 1909; its initial map has 3 Democratic-majority districts under the presidential vote model.

| Group               | Metric                        |   R-hat | Bulk ESS | Tail ESS |
| ------------------- | ----------------------------- | ------: | -------: | -------: |
| nc_block_union_2023 | Democratic-majority districts | 1.00367 |    954.0 |   1756.8 |
| nc_block_union_2023 | Efficiency gap                | 1.00238 |    822.4 |   2335.7 |
| nc_block_union_2023 | Cut edges                     | 1.00533 |   1150.0 |   2803.3 |
| nc_block_union_2023 | Mean-median                   | 1.00655 |    773.9 |   2173.1 |
| nc_block_union_2025 | Democratic-majority districts | 1.00185 |   1118.7 |   1543.3 |
| nc_block_union_2025 | Efficiency gap                | 1.00281 |    890.5 |   2415.7 |
| nc_block_union_2025 | Cut edges                     | 1.00257 |   1166.8 |   3299.0 |
| nc_block_union_2025 | Mean-median                   | 1.00628 |    967.6 |   2089.5 |
| joint               | Democratic-majority districts | 1.00268 |   2025.3 |   3267.9 |
| joint               | Efficiency gap                | 1.00274 |   1667.2 |   4707.4 |
| joint               | Cut edges                     | 1.00411 |   2239.9 |   6248.2 |
| joint               | Mean-median                   | 1.00581 |   1725.8 |   3947.6 |

- I recorded joint seat-count mean MCSE of 0.01835663; the full precision is in `results.json`.

## Limitations

- I use modeled presidential votes; sampler uniformity and full legal compliance remain outside the implemented model.
