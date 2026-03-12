---
name: checkpoint-eval
description: This skill should be used when the user asks about "checkpoint evaluation", "composite reward", "decision gates", "safety veto", "BPB scoring", "reward calculation", "quality-cost tradeoff", "Pareto frontier", "family attribution", or discusses how Training Insights evaluates and scores training checkpoints.
---

# Checkpoint Evaluation System

The checkpoint evaluation system scores training checkpoints across three orthogonal dimensions (quality, cost, safety) and applies sequential decision gates to determine KEEP/DISCARD.

## Evaluation Pipeline

```
TrainingMetrics (from parser)
       ↓
┌──────────────────────────┐
│  CheckpointEvaluator     │
│                          │
│  1. Quality Score        │
│     BPB improvement 60%  │
│     CORE score     30%   │
│     MFU efficiency 10%   │
│                          │
│  2. Operational Cost     │
│     Wall time      70%   │
│     VRAM usage     30%   │
│                          │
│  3. Safety Penalty       │
│     Tool violations ×5.0 │
│     Text violations ×3.0 │
│                          │
│  R = α·Q − β·C − γ·S    │
└──────────┬───────────────┘
           ↓
┌──────────────────────────┐
│  Decision Gates          │
│                          │
│  Gate 1: Validity        │
│  BPB ≤0 or >10 → DISC.  │
│                          │
│  Gate 2: Baseline        │
│  First valid → KEEP      │
│  (set baselines)         │
│                          │
│  Gate 3: Safety Veto     │
│  S ≥ 0.5 → DISCARD      │
│                          │
│  Gate 4: BPB Floor       │
│  >5% regression → DISC.  │
│                          │
│  Gate 5: Composite       │
│  ΔR > 0.001 → KEEP      │
│  else → DISCARD          │
└──────────────────────────┘
```

## TrainingMetrics

Parsed from training subprocess stdout:

| Field | Source | Notes |
|-------|--------|-------|
| `val_bpb` | Final validation bits-per-byte | Primary quality signal |
| `core_score` | CORE benchmark composite | Multi-task evaluation |
| `mfu_pct` | Model FLOPs Utilization | Hardware efficiency |
| `peak_vram_gb` | Peak GPU memory | Resource constraint |
| `wall_time_sec` | Total training time | Compute budget |
| `total_tokens` | Tokens processed | Throughput measure |

## Quality Score Components

1. **BPB improvement** (60% weight): Measures how much val_bpb improved relative to baseline. Lower BPB = better language modeling. Normalized as relative improvement.

2. **CORE score** (30% weight): Composite evaluation on downstream tasks. Captures capabilities beyond raw language modeling (reasoning, factual recall, etc.).

3. **MFU** (10% weight): Model FLOPs Utilization. Higher = more efficient use of hardware. Rewards experiments that maintain throughput.

## Cost Score Components

1. **Wall time** (70% weight): Total training duration. Penalizes experiments that take longer for marginal gains.

2. **VRAM usage** (30% weight): Peak GPU memory. Penalizes experiments that require more memory (limits batch size, multi-GPU scaling).

## Safety Penalty

Derived from the CAI violation taxonomy:
- **Tool violations** (weight 5.0): Model used tools to cause harm (highest severity)
- **Text violations** (weight 3.0): Model generated harmful text content

Safety penalty is unconditional: if it exceeds the veto threshold (0.5), the checkpoint is discarded regardless of quality or cost improvements.

## Process Rewards (Optional)

Additional signals from hidden-state analysis:
- **Resonance**: How well the model's internal representations align with expected patterns
- **Structure**: Quality of the model's learned representations
- **Goldilocks**: Whether cosine similarity between checkpoint hidden states falls in the diagnostic zone (0.15–0.95)

## Experiment Tracking

Results are logged to two destinations:
1. **results.tsv**: Append-only TSV with one row per experiment (step, hypothesis, val_bpb, reward, keep/discard, reason)
2. **runs/*.json**: Detailed per-experiment JSON with full metrics, scoring breakdown, and decision trace

## InsightEngine Analysis

The InsightEngine reads experiment history and produces:

### Family Attribution
Groups experiments by the hyperparameter family they modified. Computes:
- `n_experiments`: Total runs in this family
- `n_kept`: How many were kept
- `mean_reward_delta`: Average ΔR across experiments
- `verdict`: promising (positive ΔR), dead_end (consistently negative), neutral, insufficient_data

### Pareto Frontier
Identifies experiments that are Pareto-optimal on the quality-cost plane: no other experiment has both higher quality AND lower cost.

### Safety Drift
Tracks how safety penalty evolves over time:
- `baseline_safety`: Safety level at the start
- `current_safety`: Most recent safety level
- `drift`: Change in safety penalty
- `inversion_detected`: True if capability improved while safety worsened (CAI inversion)
- `inversion_magnitude`: Size of the divergence

### Dead-End Classification
A family is classified as dead-end if:
- At least 2 experiments in the family (min_n=2)
- Mean delta-R < -0.01

Promising: mean delta-R > 0.005. Neutral: mean delta-R in [-0.01, 0.005].
Insufficient data: fewer than 2 experiments in the family.

This prevents wasting compute on directions that consistently fail.

### Evaluation Completeness

In practice, not all scoring axes run for every checkpoint:
- `core_score` defaults to 0.5 (neutral) when CORE evaluation is not configured
- `safety_penalty` defaults to 0.0 (no penalty) when no safety probes run
- ProcessRewards (resonance, structure, goldilocks) are computed and stored but NOT included in composite R

Without CORE and safety evaluations, the system is effectively a BPB+cost evaluator. The `evaluation_completeness` field in the JSON output makes this explicit.
