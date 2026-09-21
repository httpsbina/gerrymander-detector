# Ensemble Validation

This module contains diagnostic and validation tools for the Texas
redistricting ensemble.

The validation is designed to test:

- convergence across independent Markov chains
- sensitivity to sample size
- autocorrelation between retained plans
- stability of ensemble statistics
- similarity between generated plans
- county splitting behavior
- district boundary stability

These diagnostics are kept separate from the primary analysis so that
methodological assumptions can be tested without changing the core
redistricting pipeline.