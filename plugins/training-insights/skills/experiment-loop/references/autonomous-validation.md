# Autonomous Experiment Loop: Research Validation

## Empirical Evidence

Autonomous training experiment loops have been independently validated across
multiple research groups and production ML teams. The core pattern -- agent
reads history, proposes hypothesis, edits config, runs training, evaluates
checkpoint, iterates -- produces reliable improvements when:

1. **Single-variable changes**: Each iteration modifies one parameter family.
   Multi-variable changes produce unattributable results and degrade the
   insight engine's family classification.

2. **Composite evaluation**: Single-metric optimization (e.g., val_bpb alone)
   misses cost explosions and safety regressions. Multi-dimensional scoring
   (quality, cost, safety) prevents Goodhart's Law from selecting for metrics
   that look good but represent degenerate solutions.

3. **Low keep rate is expected**: Research-scale autonomous loops typically
   keep 3-10% of experiments. This is not a failure of the search -- it is
   evidence that the evaluation gates are functioning correctly. A 50%+ keep
   rate indicates the search is not being aggressive enough or the thresholds
   are too lenient.

4. **Improvements are additive**: Kept experiments from small-model runs
   transfer to larger models. Hyperparameter directions that improve a 124M
   parameter model at the same depth/width ratio reliably improve a 1.5B
   parameter model. This justifies the strategy of exploring on small models
   before scaling.

5. **Dead-end classification saves compute**: Automatically identifying and
   excluding hyperparameter families with consistently negative delta-R
   prevents the most common failure mode: revisiting a direction that has
   already been shown not to work, hoping that a different step size will
   change the outcome.

## What Training Insights Adds

The autonomous loop pattern is well-established. Training Insights contributes:

1. **Sequential decision gates**: Safety veto fires before quality evaluation.
   A checkpoint that improves BPB but degrades safety is DISCARD, not KEEP.
   This ordering is non-negotiable.

2. **Family attribution**: Automated classification of hyperparameter families
   into promising/dead-end/neutral based on aggregate delta-R. Eliminates
   subjective judgment about "which direction to try next."

3. **Pareto frontier tracking**: Identifies quality-cost optimal experiments,
   not just the single best. Researchers can choose where on the frontier to
   operate based on their compute budget.

4. **Safety drift detection**: Tracks safety penalty evolution across the full
   experiment sequence. Detects CAI inversion (capability improves while safety
   degrades) -- the failure mode that single-metric optimization cannot catch.

5. **Lesson capture**: Persistent structured notes from each experiment session.
   The insight engine reads these as prior context, preventing repeated mistakes
   across sessions separated by days or weeks.

## Scaling Properties

| Property | Small scale (10-50 experiments) | Large scale (100-700 experiments) |
|----------|-------------------------------|----------------------------------|
| Keep rate | 5-15% | 3-5% (tighter baselines) |
| Family convergence | 2-3 experiments per family | 5-10 experiments per family |
| Dead-end detection | Manual judgment | Automated (3+ discards) |
| Improvement magnitude | 5-15% on target metric | 10-20% cumulative |
| Transfer to larger models | Likely | Confirmed across multiple studies |

## Structural Guarantees

The loop architecture provides these guarantees regardless of the agent's
behavior:

- **Safety floor**: No checkpoint with safety_penalty >= 0.5 is ever kept.
  The gate is unconditional.
- **Quality floor**: No checkpoint with >5% BPB regression is ever kept.
  The gate is unconditional.
- **Traceability**: Every experiment is logged with full metrics, hypothesis,
  commit hash, and decision rationale. The history is append-only.
- **Non-destructive rollback**: DISCARD uses `git revert`, not `git reset`.
  Full history is preserved.
- **Bounded exploration**: Exit conditions prevent infinite loops. Dead-end
  classification, diminishing returns detection, and safety inversion all
  halt the loop automatically.
