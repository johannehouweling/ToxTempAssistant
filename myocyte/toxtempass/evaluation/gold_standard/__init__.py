"""Gold-standard workstream: production scientist-accepted answers as ground truth.

A distinct workstream (parallel to ``real_world`` / ``positive_control`` /
``negative_control``) that treats the answers scientists reviewed and accepted in prod
— originally drafted by gpt-4o-mini — as the ground truth the evaluation otherwise lacked.

Modules:
  * ``edit_analysis`` — Django-free, unit-tested logic: era-aware draft detection +
    cosine-driven edit-typing (draft→final).
  * ``audit`` — read-only orchestrator: extracts the gold set + edit analysis, exposes
    ``run()`` (driven by the ``extract_gold_answers`` management command).

Outputs land in ``output/`` (gitignored, like the other workstreams).
"""
