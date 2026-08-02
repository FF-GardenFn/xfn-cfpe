# interp/ — Concept-Erasure Validation of RL-O-CoV

Implements the protocol pre-registered in [../exp_proposal.md](../exp_proposal.md) (2026-01-25): erase a target
concept from the residual stream while preserving its prerequisites, then test whether dialectic training lets the
model *re-derive* what it can no longer *retrieve*. Condition C — the hypothesis test — needs a trained
RL-O-CoV adapter; conditions A/B need only the base model.

| File | Implements | Proposal phase |
|------|------------|----------------|
| [concept_vectors.py](./concept_vectors.py) | Contrastive concept-vector extraction; ~2/3-depth default layer | 2 |
| [erasure.py](./erasure.py) | Residual-stream erasure hook — `steer` (the proposal's subtraction) and `project` (directional-projection removal) | 3 |
| [probes.py](./probes.py) | The four concept pairs with recall / preservation / derivation probe batteries and conservative grading | 1, 3–5 |
| [run_erasure_validation.py](./run_erasure_validation.py) | Conditions A/B/C orchestrator, JSONL artifacts, `--dry-run` | 6 |

**Status: implementation, not a result.** Nothing here has run against a model — this machine has no GPU stack,
and condition C additionally requires a completed V5 training run. `--dry-run` validates everything that can be
validated without one (erasure arithmetic 5/5, fixtures + grading 7/7, 16 probes over 4 pairs); every numeric
probe label was hand-derived before landing.

Grading is deliberately conservative: `numeric_exact` auto-grades, `keyword_heuristic` is reported as heuristic,
`manual` probes are recorded for adjudication and never auto-scored. The instrument's job is to make the A/B/C
contrast cheap to run and hard to fool, not to flatter the hypothesis.

**Where this sits in the wider program:** the coupled-objective design
([../../CAI/coupled_objective_design.md](../../CAI/coupled_objective_design.md) §3.6) measures dispositions
*behaviorally* and names the capability crossover m★ past which behavioral screening stops working; this package
is the mechanistic instrument on the far side of that hand-off — asking what lives in the weights, independent of
what the model chooses to show. Hook idioms follow the activation-steering rig in
[../../project/refusal-capability-entanglement/](../../project/refusal-capability-entanglement/).
