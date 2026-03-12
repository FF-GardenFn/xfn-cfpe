---
name: experiment-loop
description: Use when discussing "experiment loop", "training iteration", "autonomous experiments", "hyperparameter search", "hypothesis testing", "experiment pipeline", "training automation", or the Training Insights autonomous experiment workflow.
---

# Autonomous Experiment Loop

## Architecture

The experiment loop is a closed-loop control system. Each iteration reads
the full experiment history, proposes a single hypothesis, executes training,
evaluates the checkpoint against a composite reward, and feeds the result
back into the next iteration. The loop does not require human intervention
between iterations, but structural gates halt execution on safety violations
or convergence.

This is not discipline. This is architecture. The gates are not suggestions --
they are structural constraints that prevent the system from advancing past
unsafe or degenerate states.

```
                    +-----------+
                    | DIRECTION |  (researcher input or insight engine)
                    +-----+-----+
                          |
                          v
                 +--------+--------+
            +--->| ti analyze       |  Read full experiment history
            |    +--------+--------+
            |             |
            |             v
            |    +--------+--------+
            |    | Read config      |  quick_train.py constants
            |    +--------+--------+
            |             |
            |             v
            |    +--------+--------+
            |    | Propose          |  Single hypothesis, one change
            |    +--------+--------+
            |             |
            |             v
            |    +--------+--------+
            |    | Edit + commit    |  Modify constants, git commit
            |    +--------+--------+
            |             |
            |             v
            |    +--------+--------+
            |    | ti run -H "..."  |  Training subprocess
            |    +--------+--------+
            |             |
            |             v
            |    +--------+--------+
            |    | Parse stdout     |  -> TrainingMetrics
            |    +--------+--------+
            |             |
            |             v
            |    +--------+--------+
            |    | Evaluate         |  R = a*Q - b*C - g*S
            |    +--------+--------+
            |             |
            |             v
            |    +--------+--------+
            |    | Decision Gates   |  Sequential: validity -> baseline -> safety -> BPB -> composite
            |    +--------+--------+
            |             |
            |        +----+----+
            |        |         |
            |      KEEP     DISCARD
            |        |         |
            |   baseline    git revert
            |   updated        |
            |        |         |
            |        +----+----+
            |             |
            |             v
            |    +--------+--------+
            |    | Log              |  results.tsv + runs/*.json
            |    +--------+--------+
            |             |
            |             v
            |    +--------+--------+
            |    | Reflect          |  Check exit conditions
            +----+--------+--------+
                          |
                    (exit if terminal state reached)
```

## Composite Reward

```
R = alpha * quality  -  beta * cost  -  gamma * safety

alpha = 1.0    beta = 0.5    gamma = 2.0
```

### Quality (alpha = 1.0)

| Component        | Weight | Signal                                    |
|------------------|--------|-------------------------------------------|
| BPB improvement  | 60%    | Relative val_bpb reduction vs baseline    |
| CORE score       | 30%    | Multi-task downstream evaluation          |
| MFU              | 10%    | Model FLOPs Utilization (hardware efficiency) |

### Cost (beta = 0.5)

| Component   | Weight | Signal                         |
|-------------|--------|--------------------------------|
| Wall time   | 70%    | Training duration in seconds   |
| VRAM usage  | 30%    | Peak GPU memory in GB          |

### Safety (gamma = 2.0)

| Violation type | Multiplier | Description                      |
|----------------|------------|----------------------------------|
| Tool violation | 5.0        | Model used tools to cause harm   |
| Text violation | 3.0        | Model generated harmful content  |

Safety is weighted 2x the quality signal. This is intentional. A model that
scores higher on quality but regresses on safety is worse, not better.

## Decision Gate Order

Gates fire sequentially. The first gate that triggers determines the outcome.
There is no override mechanism. There is no "but the quality was really good"
exception.

```
Gate 1: VALIDITY
  Condition: val_bpb <= 0 or val_bpb > 10
  Action:    DISCARD (crash or divergence, no further evaluation)
  Rationale: Invalid metrics cannot be scored

Gate 2: BASELINE ESTABLISHMENT
  Condition: No baseline exists yet (first valid run)
  Action:    KEEP, set baseline_bpb and baseline_composite
  Rationale: First valid result anchors all subsequent comparisons

Gate 3: SAFETY VETO
  Condition: safety_penalty >= 0.5
  Action:    DISCARD unconditionally
  Rationale: No quality gain justifies safety regression

Gate 4: BPB DIVERGENCE FLOOR
  Condition: val_bpb regresses > 5% from baseline
  Action:    DISCARD
  Rationale: Language modeling capability is non-negotiable

Gate 5: COMPOSITE IMPROVEMENT
  Condition: delta_R > 0.001
  Action:    KEEP, update baseline
  Otherwise: DISCARD
  Rationale: Changes must produce measurable improvement
```

## Phase-Gated Workflow

Each phase requires artifacts from the previous phase. Proceeding without
the required artifact is a structural violation, not a judgment call.

### Phase 1: Read State

**Required input:** Experiment history (results.tsv, runs/*.json) OR empty state (first run).
**Output artifact:** Current insight summary (family verdicts, Pareto frontier, safety status).
**Gate:** Insight summary must exist before proposing a hypothesis.

### Phase 2: Propose Hypothesis

**Required input:** Phase 1 insight summary + current quick_train.py constants.
**Output artifact:** Named hypothesis with exact parameter change and rationale.
**Gate:** Hypothesis must name the parameter family, old value, new value, and expected direction.
Bad: "try different learning rate". Good: "increase embedding_lr 0.6 -> 0.8, promising family mean dR=+0.023".

### Phase 3: Execute

**Required input:** Phase 2 hypothesis committed to git.
**Output artifact:** TrainingMetrics parsed from subprocess stdout.
**Gate:** Training must complete without crash or timeout. On failure, enter diagnostic triggers.

### Phase 4: Evaluate + Log

**Required input:** Phase 3 TrainingMetrics.
**Output artifact:** Scored checkpoint (R value, gate decisions) logged to results.tsv and runs/*.json.
**Gate:** KEEP or DISCARD determined by decision gates. Baseline updated on KEEP. Git revert on DISCARD.

### Phase 5: Reflect

**Required input:** Phase 4 logged result + updated insight summary.
**Output artifact:** Decision to iterate or exit.
**Gate:** Check all four exit conditions. If none triggered, return to Phase 1.

## Diagnostic Triggers

These are automatic reflexes, not optional responses. When a condition is
detected, the corresponding action executes without deliberation.

| Trigger              | Detection                          | Action                                                    |
|----------------------|------------------------------------|-----------------------------------------------------------|
| Training crash       | Non-zero exit code                 | Log failure reason. Do NOT retry same config. Adjust hypothesis and re-enter Phase 2. |
| OOM                  | CUDA OOM in stderr                 | Reduce batch size or model width by 25%. Re-enter Phase 2. |
| Loss divergence      | val_bpb > 2x baseline              | Halve learning rate. Re-enter Phase 2.                    |
| Safety veto          | Gate 1 fires                       | DISCARD. Log safety regression. Flag for researcher review. Do NOT continue autonomously on the same family. |
| NaN loss             | NaN detected in stdout             | Reduce learning rate by 50%, add gradient clipping if absent. Re-enter Phase 2. |
| Timeout              | Wall time exceeds budget           | Log partial metrics if available. Reduce model size or training steps. Re-enter Phase 2. |

## Hyperparameter Config

All hyperparameters are constants at the top of `quick_train.py`. Nothing
else is the experiment config. Everything else is fixed infrastructure.

| Parameter        | Type   | Description                                      |
|------------------|--------|--------------------------------------------------|
| `DEPTH`          | int    | Number of transformer layers                     |
| `ASPECT_RATIO`   | float  | Width/depth tradeoff (higher = wider, shallower) |
| `HEAD_DIM`       | int    | Attention head dimension                         |
| `WINDOW_PATTERN` | str    | Attention window allocation ("SSSL", "SSLL", "SLSL") |
| `TOTAL_BATCH_SIZE` | int  | Global batch size in tokens                      |
| `embedding_lr`   | float  | Learning rate for embedding layer                |
| `unembedding_lr` | float  | Learning rate for unembedding layer              |
| `matrix_lr`      | float  | Learning rate for weight matrices                |
| `scalar_lr`      | float  | Learning rate for scalar parameters              |
| `WEIGHT_DECAY`   | float  | Muon cautious weight decay (sign-matched)        |
| `WARMDOWN_RATIO` | float  | LR cooldown schedule proportion                  |

## Priority Order

Ranked by signal-to-noise ratio. Explore top of list first. Do not skip to
lower-priority parameters unless higher-priority families are exhausted or
classified as dead-end.

| Rank | Family          | Rationale                                                  |
|------|-----------------|------------------------------------------------------------|
| 1    | Learning rates  | 4-group structure. Highest signal-to-noise. Most publications tune this first. |
| 2    | Window pattern  | Attention budget allocation. Discrete search space, fast feedback. |
| 3    | Batch size      | Gradient smoothing vs update frequency. Strong interaction with LR. |
| 4    | Depth vs width  | ASPECT_RATIO. Structural change -- larger impact, higher risk. |
| 5    | Warmdown ratio  | LR cooldown. Secondary effect after LR magnitude is settled. |
| 6    | Weight decay    | Regularization. Lowest priority -- rarely the bottleneck.   |

## Insight Engine

The insight engine reads the full experiment history after every iteration
and produces five outputs.

### Family Attribution

Groups experiments by the hyperparameter family they modified. For each family:
- `n_experiments`: Total runs in the family.
- `n_kept`: How many passed all gates.
- `mean_reward_delta`: Average delta-R across all experiments in the family.
- `verdict`: One of `promising` (mean delta-R > 0.005), `dead_end` (>= 2 experiments, mean delta-R < -0.01), `neutral` (mean delta-R in [-0.01, 0.005]), `insufficient_data` (< 2 experiments).

### Pareto Frontier

Identifies experiments that are Pareto-optimal on the quality-cost plane.
An experiment is on the frontier if no other experiment has both higher
quality AND lower cost. Used to identify the best achievable tradeoff.

### Safety Drift

Tracks safety penalty evolution over the experiment sequence:
- `baseline_safety`: Safety level at experiment 0.
- `current_safety`: Most recent safety level.
- `drift`: Signed change in safety penalty.
- `inversion_detected`: True when capability improved while safety worsened (CAI inversion).
- `inversion_magnitude`: Size of the divergence.

When inversion is detected, the loop halts and flags for researcher review.

### Dead-End Classification

A family is classified as dead-end when:
1. At least 2 experiments in the family (min_n=2).
2. Mean delta-R < -0.01.

Dead-end families are excluded from hypothesis generation. This prevents
wasting compute on directions that consistently fail.

### Next Hypothesis Context

Synthesizes all available data into a recommendation for the next experiment.
Considers: family verdicts, Pareto gaps, safety status, unexplored regions
of the parameter space, and the researcher's stated direction.

## Exit Conditions

Four terminal states. When any is reached, the loop halts. These are
structural constraints, not heuristics.

| Terminal State       | Condition                                           | Action                                |
|----------------------|-----------------------------------------------------|---------------------------------------|
| Direction exhausted  | 2-3 parameter values explored for the current direction | Report findings, await new direction  |
| Dead-end confirmed   | Insight engine classifies family as dead-end        | Report classification with evidence   |
| Diminishing returns  | |delta-R| < 0.001 for 3 consecutive experiments in the same family | Report plateau, suggest new family    |
| Safety inversion     | CAI inversion detected by insight engine            | HALT. Report to researcher. Do NOT continue autonomously. |

## Lesson Capture Protocol

Persistent learning across sessions. After each loop termination (not each
iteration -- after the full loop exits), capture a structured lesson.

### Lesson Format

```
## Lesson: [family] -- [direction] -- [date]

Direction: <researcher's original direction>
Experiments run: <N>
Kept / Discarded: <K> / <D>
Best delta-R: <value> (experiment <id>)
Family verdict: <promising | dead_end | neutral>

What worked: <1-2 sentences>
What failed: <1-2 sentences>
Structural insight: <what this reveals about the loss landscape>
Next time: <what to do differently if revisiting this family>
```

### Storage

Lessons append to `$TI_ROOT/lessons.md`. This file persists across sessions
and is read by the insight engine as prior context when generating the next
hypothesis.

## CLI Reference

| Command                                              | Description                              |
|------------------------------------------------------|------------------------------------------|
| `ti run -H "hypothesis" --train-cmd "..." --cwd "..."` | Run one experiment (full pipeline)       |
| `ti run --loop --max-experiments N`                  | Autonomous loop mode (N iterations max)  |
| `ti analyze`                                         | Extract insights from experiment history |
| `ti status`                                          | Experiment dashboard with family table   |
| `ti report --latest`                                 | Markdown report for most recent experiment |
| `ti report --step N`                                 | Markdown report for experiment N         |

## Retry Protocol

After DISCARD, the next iteration is structurally different from the previous
one. The retry protocol enforces this.

### What changes after DISCARD

1. **Config reverts**: `git revert HEAD` restores quick_train.py to pre-experiment state.
2. **Insight engine updates**: The discarded experiment is now part of the history. Family statistics, Pareto frontier, and safety drift all incorporate the new data point.
3. **Hypothesis must differ**: The next hypothesis cannot be identical to the discarded one. If the same parameter is being explored, the value must change. If the value was too aggressive, try a smaller step. If the direction was wrong, try the opposite.
4. **Diagnostic trigger output feeds Phase 2**: If the discard was caused by a diagnostic trigger (crash, OOM, divergence), the trigger's prescribed action constrains the next hypothesis.

### What does NOT change after DISCARD

- The baseline remains unchanged (only KEEP updates the baseline).
- The decision gate thresholds remain unchanged.
- The priority order remains unchanged.
- Infrastructure code (core/, tasks/, evaluation/) remains untouched.

### Escalation

If 3 consecutive experiments in the same family are discarded, the family
is approaching dead-end classification. The next action is to move to the
next family in the priority order, not to try a fourth time.
