# Geographic measures

I am testing why the enacted maps have low population-clustering scores but high mean perimeter compactness. The starting comparison uses the same frozen assignments and the same Census-block measurement geography for every plan; the calculations do not use votes or party labels.

Cut-edge count and physical boundary length measure different quantities. Tapp describes how dense urban tilings can receive a larger penalty from counting adjacencies, while length-based scores give more weight to long rural boundaries; the paper develops a population-density weighting that connects the two. I use that weighting to score saved plans, leaving the sampler unchanged. [Revisiting compactness for district plans](https://arxiv.org/html/2501.02325).

Barnes and Solomon show that boundary detail, holes, disconnected components and other implementation choices affect compactness scores. I therefore keep the measurement geometry fixed and report alternative weightings separately. [Gerrymandering and Compactness: Implementation Flexibility and Abuse](https://arxiv.org/html/1803.02857).

## Boundary weighting

For each pair of adjacent measurement pieces, I retain the shared-boundary length, combined population and combined area. I calculate the number of cut adjacencies, total internal boundary length and a density-weighted length:

\[
L_\rho = \sum_{e\ \mathrm{cut}} l_e\sqrt{\frac{p_i+p_j}{A_i+A_j}}.
\]

The density-weighted quantity is an approximation based on the two adjacent pieces; it has different units from ordinary length, so I compare ranks within a state. Every map uses the same fixed weights, based on 2020 Census population. An adjacency between two zero-population pieces receives zero density weight, while remaining in the unweighted count and physical-length measurements. I also report cut rates in five fixed density bins, including zero-population pieces.

The common measurement graph differs from the original simulation graph, particularly where Texas enacted assignments split simulation units. I name those cut counts separately, and retain the sampler's stored cut-edge counts for comparisons among simulated plans. Texas enacted assignments remain at block resolution. Some enacted lines cut inside simulation units, while the stored maps cannot cut there; I therefore report within-unit and between-unit components separately. I retain the raw count as well, since the between-unit component is a sensitivity measurement rather than a replacement score.

## Area and population

I calculate a uniform-area radius by integrating polygon interiors, subtracting holes and preserving every component. This gives a geometric counterpart to the population-weighted block-centroid radius. I also compare the mean, median and area-weighted mean of district Polsby-Popper scores to check whether aggregation explains the apparent perimeter advantage.

For population dispersion, I group Census-block moments by county and measurement piece, then calculate each county's contribution to the statewide squared normalized radius. These contributions add exactly; their enacted-minus-ensemble differences identify where the population-distance gap occurs. Half-history differences identify which counties contribute to changes within a chain. They describe distances to district centers, rather than distances to county centers.

The centroid approximation has one useful algebraic property. If I assume population is uniformly distributed inside each block, the within-block variance adds the same constant, K, to every plan's within-district and statewide sums of squares. The normalized radius becomes sqrt((SSW + K) / (SST + K)), so this particular correction preserves plan rankings. Actual resident locations within blocks remain unknown.

## Limitations

These analyses describe the existing constrained ensemble. They do not identify intent or establish legal compliance, and the new geographic metrics have unresolved convergence. Uniform-area weighting includes every area represented by the source blocks, including water; it is not a land-only measure. A difference between population and area weighting is not a causal estimate, and county contributions can offset one another. The block-uniform variance argument applies to that specified population model, rather than every possible distribution of residents.

## Records

The initial all-checkpoint results are in paper/reviews/geographic-validation-20261109/validated. The weighting and county calculations are produced by paper/compactness_mechanisms.py in a separate directory, with source hashes, package versions, diagnostics and validation identities recorded in results.json. Neither analysis changes the original freezes.
