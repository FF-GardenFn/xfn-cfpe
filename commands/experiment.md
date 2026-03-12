# /experiment — Autonomous Training Experiment

You are the agent brain in an autonomous training experiment loop. The researcher
gives a direction; you read insights, propose hypotheses, modify hyperparameters,
run training, evaluate results, and iterate.

**Researcher's direction**: $ARGUMENTS

## Environment Setup

```bash
export TI_ROOT="/Users/hyperexploiter/PycharmProjects/XFN-CFPE /training_insights"
export PYTHONPATH="/Users/hyperexploiter/PycharmProjects/XFN-CFPE :$PYTHONPATH"
export PYTHON="$TI_ROOT/../bin/python3"
```

All `ti` commands: `cd "$TI_ROOT" && PYTHONPATH="/Users/hyperexploiter/PycharmProjects/XFN-CFPE " $PYTHON -m training_insights <command>`

## Your Loop

Repeat until the researcher's direction is explored (typically 3-5 experiments):

### Step 1: Read Insights

```bash
cd "$TI_ROOT" && PYTHONPATH="/Users/hyperexploiter/PycharmProjects/XFN-CFPE " $PYTHON -m training_insights analyze
```

This prints:
- **Promising families**: positive mean ΔR — explore these first
- **Dead-end families**: consistently negative ΔR — skip
- **Safety status**: if CAI inversion detected, prioritise safe experiments
- **Top-3 kept experiments**: what worked best so far
- **Suggested next direction**: where the insight engine thinks you should go

If no experiments exist yet, run a baseline first.

### Step 2: Read Current Config

Read `$TI_ROOT/quick_train.py` — hyperparameters are **constants at the top**:
`DEPTH`, `ASPECT_RATIO`, `HEAD_DIM`, `WINDOW_PATTERN`, `TOTAL_BATCH_SIZE`,
learning rates (`embedding_lr`, `unembedding_lr`, `matrix_lr`, `scalar_lr`),
`WEIGHT_DECAY`, `WARMDOWN_RATIO`, etc.

These constants ARE the experiment config. You edit them, nothing else.

### Step 3: Propose + Edit + Commit

Turn the researcher's direction into a specific, measurable change.

**Be precise in hypothesis naming** — the insight engine classifies experiments
by family (learning_rate, window_pattern, batch_size, depth, width, etc.):
- GOOD: `"increase embedding_lr 0.6 → 0.8 — promising family, mean ΔR=+0.023"`
- BAD: `"try different learning rate"`

Make **ONE change** (or small related group) in `quick_train.py`. Then:
```bash
cd "$TI_ROOT" && git add quick_train.py && git commit -m "experiment: <hypothesis>"
```

### Step 4: Run Training + Evaluate

```bash
cd "$TI_ROOT" && PYTHONPATH="/Users/hyperexploiter/PycharmProjects/XFN-CFPE " $PYTHON -m training_insights run \
  -H "your hypothesis here" \
  --train-cmd "$PYTHON quick_train.py" \
  --cwd "$TI_ROOT"
```

This single command does everything:
1. Runs training subprocess (with timeout)
2. Parses stdout → TrainingMetrics (val_bpb, MFU, VRAM, wall time)
3. Computes composite reward: R = α·quality − β·cost − γ·safety
4. Applies decision gates in order:
   - Safety veto (penalty ≥ 0.5 → DISCARD unconditionally)
   - BPB divergence floor (> 5% regression → DISCARD)
   - Composite improvement (ΔR > 0.001 → KEEP, baseline updated)
5. Logs to results.tsv + runs/*.json
6. Git revert on DISCARD (non-destructive)

### Step 5: Reflect + Iterate

Re-run `ti analyze` (Step 1). Check:
- Did the family verdict change? (neutral → promising, or → dead-end)
- Did the Pareto frontier shift?
- Is the researcher's direction exhausted, or should you try another value?
- What does the insight engine suggest next?

Then go back to Step 3 with the next hypothesis, or stop if converged.

## What You Can Edit

- `$TI_ROOT/quick_train.py` — hyperparameter constants at top (the config)
- `$TI_ROOT/scripts/base_train.py` — multi-GPU trainer (use `--train-cmd "torchrun ..."`)

## What You Must NOT Edit

- `$TI_ROOT/core/` — model architecture, optimizer, data pipeline
- `$TI_ROOT/tasks/` — evaluation tasks
- `$TI_ROOT/evaluation/` — scoring pipeline
- These are fixed for fair comparison across experiments.

## Scoring Reference

```
R = α·quality − β·cost − γ·safety

quality (α=1.0):  BPB improvement (60%) + CORE score (30%) + MFU (10%)
cost    (β=0.5):  wall time (70%) + VRAM usage (30%)
safety  (γ=2.0):  CAI violation taxonomy (tool=5.0, text=3.0 per violation)
```

## Hyperparameter Priority Order

1. **Learning rates**: 4-group structure (embedding, unembedding, matrix, scalar)
2. **Window pattern**: SSSL, SSLL, SLSL — attention budget allocation
3. **Batch size**: gradient smoothing vs update frequency
4. **Depth vs width**: ASPECT_RATIO tradeoff
5. **Warmdown ratio**: LR cooldown schedule
6. **Weight decay**: Muon cautious WD (sign-matched)

## When to Stop

- The researcher's direction has been explored across 2-3 parameter values
- The insight engine classifies the family as dead-end (consistently negative ΔR)
- Successive experiments show diminishing returns (ΔR < 0.001)
- Safety inversion is detected — report to researcher before continuing