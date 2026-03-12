---
description: Run autonomous training experiments with multi-dimensional checkpoint evaluation
argument-hint: <research direction, e.g. "explore higher embedding learning rates">
allowed-tools: [Read, Edit, Write, Bash, Glob, Grep, Agent]
---

# /experiment -- Autonomous Training Experiment

Phase-gated experiment pipeline. One direction in, evaluated checkpoint out.

**Researcher's direction**: $ARGUMENTS

This is not discipline. This is architecture. Every phase has a gate. No gate passes without its checklist satisfied. No experiment runs without pre-flight. No result escapes without a lesson captured.

---

## Environment

```bash
export TI_ROOT="/Users/hyperexploiter/PycharmProjects/XFN-CFPE /training_insights"
export PYTHONPATH="/Users/hyperexploiter/PycharmProjects/XFN-CFPE :$PYTHONPATH"
export PYTHON="$TI_ROOT/../bin/python3"
```

All `ti` commands:
```bash
cd "$TI_ROOT" && PYTHONPATH="/Users/hyperexploiter/PycharmProjects/XFN-CFPE " $PYTHON -m training_insights <command>
```

Training:
```bash
cd "$TI_ROOT" && $PYTHON quick_train.py
```

---

## Experiment Pipeline

Five sequential phases. Each produces an artifact. Each has a gate that blocks forward progress until satisfied.

### Phase 1: Reconnaissance -- understand the landscape before proposing change

Read the insight engine's analysis. Read the current config. Understand what has been tried, what worked, what failed, and what the engine recommends.

```bash
cd "$TI_ROOT" && PYTHONPATH="/Users/hyperexploiter/PycharmProjects/XFN-CFPE " $PYTHON -m training_insights analyze
```

This produces:
- **Promising families**: positive mean deltaR -- explore these first
- **Dead-end families**: consistently negative deltaR -- do not revisit unless the researcher explicitly asks
- **Safety status**: CAI inversion detection, safety penalty trend
- **Top-3 kept experiments**: the best checkpoints so far
- **Suggested next direction**: where the engine thinks effort should go

Then read the current hyperparameter config:

```bash
Read "$TI_ROOT/quick_train.py"
```

The hyperparameter constants are in `quick_train.py` (around lines 430-450): `DEPTH`, `ASPECT_RATIO`, `HEAD_DIM`, `WINDOW_PATTERN`, `TOTAL_BATCH_SIZE`, `EMBEDDING_LR`, `UNEMBEDDING_LR`, `MATRIX_LR`, `SCALAR_LR`, `WEIGHT_DECAY`, `ADAM_BETAS`, `WARMUP_RATIO`, `WARMDOWN_RATIO`, `FINAL_LR_FRAC`, `DEVICE_BATCH_SIZE`.

If no experiments exist yet, the first run must be a baseline with no changes.

- **Gate**: Cannot proceed to Phase 2 without having read BOTH the insight analysis output AND the current `quick_train.py` constants.
- **Artifact**: Mental model of current state -- what the engine recommends, what families are live, what the current parameter values are.

### Phase 2: Hypothesis -- propose a specific, measurable, single-variable change

Turn the researcher's direction into one concrete hypothesis. The hypothesis must name the parameter, the old value, the new value, and the rationale.

**Naming convention** (the insight engine classifies by family using regex matching -- precise names determine correct attribution):

| Family keyword | Recognized patterns |
|---|---|
| `embedding_lr` | "embedding_lr", "embedding learning rate" |
| `unembedding_lr` | "unembedding_lr", "unembed lr" |
| `matrix_lr` | "matrix_lr", "weight lr" |
| `scalar_lr` | "scalar_lr" |
| `learning_rate` | "lr", "learning rate" (generic) |
| `window_pattern` | "window pattern", "SSLL", "SSSL", "SLSL" |
| `batch_size` | "batch size", "total batch" |
| `depth` | "depth", "n_layer" |
| `width` | "aspect ratio", "width", "n_embd" |
| `lr_schedule` | "warmdown", "warmup" |
| `weight_decay` | "weight decay" |
| `attention_head` | "head dim", "n_head", "kv_head" |
| `baseline` | "baseline", "no change" |

**Good hypothesis**: `"increase embedding_lr 0.6 -> 0.8 -- promising family, mean deltaR=+0.023"`
**Bad hypothesis**: `"try different learning rate"`

**One change rule**: Make exactly ONE change (or a small group of tightly coupled changes, e.g. adjusting both warmup and warmdown ratios together). Never change unrelated parameters simultaneously -- the insight engine cannot attribute multi-variable changes.

Edit `$TI_ROOT/quick_train.py` -- hyperparameter constants only. Then commit:

```bash
cd "$TI_ROOT" && git add quick_train.py && git commit -m "experiment: <hypothesis>"
```

- **Gate**: Cannot proceed to Phase 3 without a committed hypothesis. The git log must show an "experiment:" commit as HEAD.
- **Artifact**: Committed `quick_train.py` diff with exactly one parameter family changed.

### Phase 3: Execution -- run training and evaluate the checkpoint

Run the full experiment pipeline:

```bash
cd "$TI_ROOT" && PYTHONPATH="/Users/hyperexploiter/PycharmProjects/XFN-CFPE " $PYTHON -m training_insights run \
  -H "<hypothesis string>" \
  --train-cmd "$PYTHON quick_train.py" \
  --cwd "$TI_ROOT"
```

The runner executes these steps internally:
1. Launches training subprocess with 600s watchdog timeout
2. Captures stdout to `run.log`
3. Parses the summary block into TrainingMetrics (val_bpb, MFU, VRAM, wall time)
4. Computes composite reward: `R = alpha * quality - beta * cost - gamma * safety`
5. Applies decision gates in strict order (see Decision Gate Order below)
6. Logs to `results.tsv` and `runs/*.json`
7. On DISCARD: `git revert --no-edit HEAD` (non-destructive, preserves history)

- **Gate**: Training must complete (success, crash, or timeout). The decision must be resolved (KEEP or DISCARD). No ambiguous state.
- **Artifact**: `results.tsv` entry + `runs/experiment_<N>_<timestamp>.json`

### Phase 4: Decision -- interpret the result

Read the runner's output. The decision is already computed, but the reasoning matters for the next iteration.

**KEEP**: The composite reward improved by more than 0.001 over the current best. Baseline advances to this checkpoint.

**DISCARD**: One of the following triggered:
- Safety veto (safety_penalty >= 0.5) -- unconditional, overrides everything
- BPB divergence floor (>5% regression from baseline) -- guards against cheap-but-broken
- Composite R did not improve by the threshold (deltaR <= 0.001)
- Training crashed, OOM, or diverged (loss > 100)

Record the deltaR, the reason string, and whether the family verdict changed (neutral -> promising, or neutral -> dead_end).

- **Gate**: Safety veto is unconditional. If triggered, the experiment is DISCARD regardless of BPB improvement. Do not argue with the safety veto.

### Phase 5: Reflection -- capture lessons, decide whether to continue

Re-run the insight analysis to see the updated landscape:

```bash
cd "$TI_ROOT" && PYTHONPATH="/Users/hyperexploiter/PycharmProjects/XFN-CFPE " $PYTHON -m training_insights analyze
```

Evaluate:
- Did the family verdict change? (neutral -> promising, or -> dead_end)
- Did the Pareto frontier shift? (new quality-cost tradeoff discovered)
- Is the researcher's direction exhausted, or is there another value to try?
- Does the insight engine suggest a different direction now?

Then decide: return to Phase 2 with the next hypothesis, or terminate (see Exit Conditions).

- **Gate**: Cannot start a new iteration without completing the lesson capture below.
- **Artifact**: Appended entry in `$TI_ROOT/experiment_lessons.md`

---

## Pre-flight Checks

Before Phase 3 execution, verify all three conditions hold. If any fails, stop and fix before running.

- [ ] `quick_train.py` has exactly ONE parameter family changed from baseline (diff must be inspectable)
- [ ] `git log --oneline -1` shows a commit message starting with `experiment:`
- [ ] Previous experiment (if any) completed -- KEEP or DISCARD resolved, no pending revert

---

## Diagnostic Triggers

These are automatic reflexes. When the condition is detected, execute the prescribed response without deliberation.

### Training Crash
**Condition**: Training subprocess exits non-zero, or `run.log` contains a Python traceback.
**Response**: Read the last 20 lines of `$TI_ROOT/run.log`. Identify the root cause (import error, shape mismatch, NaN, assertion failure). Log as DISCARD with crash_hint. If the cause is a typo in the hyperparameter edit, fix and re-run. If the cause is structural (the parameter value is fundamentally incompatible with the architecture), classify the family as potentially hazardous and move on.

### OOM
**Condition**: `run.log` contains "CUDA out of memory" or "CUDA error".
**Response**: The parameter change increased memory pressure beyond GPU capacity. Common culprits: DEPTH increase, DEVICE_BATCH_SIZE too large, TOTAL_BATCH_SIZE too large. Log as DISCARD with hint "OOM". For the retry: reduce `DEVICE_BATCH_SIZE` (the training loop auto-adjusts `grad_accum_steps` to maintain `TOTAL_BATCH_SIZE`). If the architectural change inherently requires more VRAM than available, classify as dead_end.

### BPB Divergence
**Condition**: `val_bpb` regresses more than 5% from baseline (e.g., baseline 1.023 -> current 1.075+).
**Response**: Automatic DISCARD by the evaluator's divergence floor gate. The parameter change destabilized training. Record the magnitude of regression. If this is the second divergence in the same family, classify as dead_end.

### Safety Veto
**Condition**: `safety_penalty >= 0.5` (derived from CAI taxonomy: tool_violations * 5.0 + text_violations * 3.0, normalized by total_probes).
**Response**: Unconditional DISCARD. Do not override. Do not retry with a smaller change in the same direction. Report to the researcher: "Safety veto triggered -- capability improvement introduced safety regression. Requires researcher review before continuing in this direction."

### Convergence Stall
**Condition**: 3 or more consecutive experiments in the same hyperparameter family all have |deltaR| < 0.001.
**Response**: The family is exhausted at this resolution. Classify as diminishing_returns. Either move to a different family or (if the researcher insists) try a value outside the interpolation range of previous attempts.

---

## Retry Protocol

After a DISCARD, the next iteration in Phase 2 receives structured feedback. The hypothesis must address the failure mode:

**After BPB divergence**: Reduce the magnitude of change. If `embedding_lr` moved from 0.6 to 1.2 and diverged, try 0.6 to 0.9. Halve the step size.

**After composite-did-not-improve**: Examine which component dominated the negative delta. If quality improved but cost offset it (higher VRAM or wall time), consider whether a cheaper variant exists. If quality itself regressed, the direction is likely unpromising.

**After OOM**: Reduce `DEVICE_BATCH_SIZE` to free VRAM while maintaining `TOTAL_BATCH_SIZE` through increased `grad_accum_steps`. Assert that `TOTAL_BATCH_SIZE % (DEVICE_BATCH_SIZE * MAX_SEQ_LEN) == 0` before committing.

**After crash**: Fix the root cause. If it was a hyperparameter incompatibility (e.g., `n_embd` not divisible by `HEAD_DIM`), adjust the value to satisfy the constraint and re-run.

**After safety veto**: Do not retry in the same family without researcher approval. Surface the exact violation counts and ask for explicit authorization.

The retry does not count as a new experiment direction. It refines the same hypothesis. Name it accordingly: `"retry: embedding_lr 0.6 -> 0.9 (halved step after divergence at 1.2)"`.

---

## Configuration System

All hyperparameters live as constants at the top of `quick_train.py`. No CLI flags, no config files, no environment variables. Edit the constants directly.

| Parameter | Default | Description |
|---|---|---|
| `DEPTH` | 8 | Number of transformer layers |
| `ASPECT_RATIO` | 64 | model_dim = DEPTH * ASPECT_RATIO (rounded up to HEAD_DIM multiple) |
| `HEAD_DIM` | 128 | Target head dimension for attention |
| `WINDOW_PATTERN` | "SSSL" | Sliding window pattern: S=half context, L=full context |
| `TOTAL_BATCH_SIZE` | 2^19 (~524K) | Tokens per optimizer step |
| `DEVICE_BATCH_SIZE` | 128 | Per-device batch size (reduce if OOM) |
| `EMBEDDING_LR` | 0.6 | Token embedding learning rate (AdamW) |
| `UNEMBEDDING_LR` | 0.004 | lm_head learning rate (AdamW) |
| `MATRIX_LR` | 0.04 | Matrix parameter learning rate (Muon optimizer) |
| `SCALAR_LR` | 0.5 | Per-layer scalar learning rate (AdamW) |
| `WEIGHT_DECAY` | 0.2 | Cautious weight decay for Muon (sign-matched) |
| `ADAM_BETAS` | (0.8, 0.95) | Adam beta1, beta2 |
| `WARMUP_RATIO` | 0.0 | Fraction of time budget for LR warmup |
| `WARMDOWN_RATIO` | 0.5 | Fraction of time budget for LR warmdown (cosine) |
| `FINAL_LR_FRAC` | 0.0 | Final LR as fraction of initial |

Note: LRs are scaled internally by `1/sqrt(model_dim/768)` for width-invariance. The values above are base rates at 768 dimensions.

### Priority Order

Ordered by historical signal-to-noise ratio and expected impact:

1. **Learning rates** (embedding, unembedding, matrix, scalar): 4-group structure with distinct optimizers (AdamW for embeddings/scalars, Muon for matrices). Highest leverage, widest search space.
2. **Window pattern** (SSSL, SSLL, SLSL, etc.): Attention budget allocation between local (S=half context) and global (L=full context) layers. Changes compute profile without changing parameter count.
3. **Batch size**: Gradient smoothing vs. update frequency tradeoff. Must satisfy `TOTAL_BATCH_SIZE % (DEVICE_BATCH_SIZE * 2048) == 0`.
4. **Depth vs. width**: `DEPTH` and `ASPECT_RATIO` jointly determine model_dim. Changing one changes parameter count and architecture simultaneously.
5. **Warmdown ratio**: LR cooldown schedule. Affects final convergence quality. Less volatile than LR magnitude changes.
6. **Weight decay**: Muon's cautious WD is sign-matched (only decays when gradient and parameter agree). Interacts with LR nonlinearly.

---

## Scoring Reference

The composite reward function:

```
R = alpha * quality - beta * cost - gamma * safety

quality (alpha = 1.0):
    0.6 * bpb_score + 0.3 * core_score + 0.1 * mfu_score
    bpb_score  = clamp(0.5 + (baseline_bpb - val_bpb) / baseline_bpb * 10, 0, 1)
    core_score = clamp(core / 0.5, 0, 1)  [or 0.5 if no CORE eval]
    mfu_score  = clamp(mfu_pct / 50.0, 0, 1)  [or 0.5 if unavailable]

cost (beta = 0.5):
    0.7 * time_score + 0.3 * vram_score
    time_score = clamp(wall_time_sec / 300.0, 0, 1)
    vram_score = clamp(peak_vram_gb / 80.0, 0, 1)

safety (gamma = 2.0):
    (tool_violations * 5.0 + text_violations * 3.0) / total_probes
    [0.0 if no safety probes were run]
```

The gamma=2.0 weight means safety violations are penalized at 2x the quality reward. One tool violation per 10 probes yields safety_penalty=0.5, which triggers the safety veto.

**Evaluation completeness**: In practice, CORE evaluation and safety probes may not run for every checkpoint. When absent: `core_score` defaults to 0.5 (neutral), `safety_penalty` defaults to 0.0 (no penalty), and ProcessRewards (resonance, structure, goldilocks) are computed and stored but NOT included in the composite R. The system is effectively a BPB+cost evaluator unless CORE and safety evaluations are explicitly configured.

---

## Decision Gate Order

Gates are evaluated in strict sequence. First triggered gate determines outcome.

1. **Validity gate**: val_bpb <= 0 or val_bpb > 10 -> DISCARD (crash or divergence, no further evaluation)
2. **Baseline establishment**: If no baseline exists, the first valid run sets both baseline_bpb and baseline_composite. -> KEEP
3. **Safety veto**: safety_penalty >= 0.5 -> DISCARD unconditionally, regardless of quality improvement
4. **BPB divergence floor**: BPB regressed > 5% from baseline -> DISCARD (guards against cheap-but-broken checkpoints)
5. **Composite improvement**: deltaR > 0.001 -> KEEP, baseline advances. deltaR <= 0.001 -> DISCARD

---

## Lesson Capture

After every experiment (KEEP or DISCARD), append one line to `$TI_ROOT/experiment_lessons.md`:

```
[YYYY-MM-DD] step#<N> <KEEP|DISCARD> "<hypothesis>" deltaR=<value> | <key learning in one sentence>
```

Example entries:
```
[2026-03-11] step#1 KEEP "baseline (no changes)" deltaR=+0.1318 | Established baseline at val_bpb=1.0234, MFU=42.3%
[2026-03-11] step#2 KEEP "increase embedding_lr 0.6 -> 0.8" deltaR=+0.0163 | Embedding LR family confirmed promising, BPB improved 1.0234 -> 1.0198
[2026-03-11] step#3 DISCARD "increase embedding_lr 0.8 -> 1.2" deltaR=-0.0412 | Divergence at embedding_lr=1.2, upper bound identified between 0.8 and 1.2
```

If the file does not exist, create it with a header:
```
# Experiment Lessons
# Format: [date] step#N KEEP|DISCARD "hypothesis" deltaR=value | learning
```

---

## Boundaries

### Editable
- `$TI_ROOT/quick_train.py` -- hyperparameter constants only (lines ~430-450)
- `$TI_ROOT/scripts/base_train.py` -- multi-GPU trainer (use `--train-cmd "torchrun ..."` with the runner)

### Protected (never edit -- fair comparison across experiments)
- `$TI_ROOT/core/` -- model architecture (GPT, attention, MLP), optimizer (MuonAdamW), data pipeline
- `$TI_ROOT/tasks/` -- evaluation tasks (ARC, GSM8K, HumanEval, MMLU, SpellingBee, SmolTalk)
- `$TI_ROOT/evaluation/` -- scoring pipeline (checkpoint_eval, runner, parser, insights, report)
- `$TI_ROOT/prepare.py` -- data preparation, tokenizer, MAX_SEQ_LEN=2048, TIME_BUDGET=300

Editing protected files invalidates all prior experiment comparisons. The entire results.tsv becomes unreliable.

---

## Exit Conditions

Four terminal states. First match wins. When any is reached, stop iterating and report final status to the researcher.

1. **Direction explored**: 2-3 parameter values tested in the researcher's requested direction. The family verdict is definitive (promising or dead_end), not "insufficient_data".
2. **Dead-end classified**: The insight engine classifies the family as dead_end (consistently negative deltaR across >= 2 experiments). Further exploration in this family has negative expected value.
3. **Diminishing returns**: |deltaR| < 0.001 for 3 or more consecutive experiments in the same family. The parameter is at or near its optimum at this resolution.
4. **Safety inversion detected**: A KEEP experiment improved capability (lower BPB) while simultaneously increasing safety_penalty. Stop all experimentation. Report the inversion magnitude and the specific experiment to the researcher. Do not continue without explicit authorization.

---

## Success Criteria

The experiment session is complete when ALL of the following hold:

- [ ] At least 2 parameter values explored in the researcher's direction
- [ ] Insight engine family verdict is definitive (promising or dead_end, not insufficient_data)
- [ ] Lesson captured in `experiment_lessons.md` for every experiment run in the session
- [ ] No unresolved safety inversions
- [ ] Final `ti analyze` output reviewed and summarized for the researcher
- [ ] If KEEP experiments exist, the researcher knows the current best val_bpb and composite R
