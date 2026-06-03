"""Cross-family LLM-judge panel + dependence-aware aggregation for Tier 3.

Reference-free relevance and faithfulness for the real-world (cross-provider)
evaluation are scored by a panel of judges drawn from model families NOT under
test, then aggregated with estimators that account for correlated judge errors.

This package is self-contained and additive: importing it has no effect on the
existing single-judge Tier 3 path until ``tier3_metrics`` opts in.
"""
