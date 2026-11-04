# Texas findings

- I used the first 45,000 recorded states per chain, retaining 356,000 states after 500 warmup states per chain.
- PLANC2333 scores 8 Democratic-majority districts under the modeled presidential votes, using the block-resolution audit.
- I counted 29 states at or below that score among 178,000 retained baseline states; the mean Democratic seat count is 12.85929.
- I counted 26 states at or below that score among 178,000 retained dispersed states; the mean Democratic seat count is 12.85037.
- I recorded these failing baseline primary screens: Cut edges (R-hat 1.01091, bulk ESS 449.2, tail ESS 1636.2); Mean-median (R-hat 1.01608, bulk ESS 590.5, tail ESS 1456.4).
- I recorded these failing dispersed primary screens: Cut edges (R-hat 1.02169, bulk ESS 562.4, tail ESS 2254.1).
- I recorded these failing joint primary screens: Cut edges (R-hat 1.01526, bulk ESS 936.0, tail ESS 3480.5); Mean-median (R-hat 1.01098, bulk ESS 1077.6, tail ESS 3085.1).
- I recorded baseline cut edges R-hat from 1.13644 to 1.01091 across 15 audit lengths, with 2 rising intervals.
- I recorded baseline mean-median R-hat from 1.05979 to 1.01608 across 15 audit lengths, with 6 rising intervals.
- I recorded dispersed cut edges R-hat from 1.06827 to 1.02169 across 9 audit lengths, with 2 rising intervals.
- I recorded dispersed mean-median R-hat from 1.10288 to 1.00640 across 9 audit lengths, with 2 rising intervals.
- I recorded joint cut edges R-hat from 1.01554 to 1.01526 across 2 audit lengths, with 0 rising intervals.
- I recorded joint mean-median R-hat from 1.02110 to 1.01098 across 2 audit lengths, with 0 rising intervals.

## Limitations

I use modeled election allocations with the recorded ReCom population and contiguity constraints. The states are autocorrelated, and these counts are descriptive frequencies; zero observations do not imply zero probability. I have not established uniform sampling or full legal compliance.
