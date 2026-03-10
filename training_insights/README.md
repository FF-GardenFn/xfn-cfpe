# Training Insights (WIP)

Autonomous LLM training experiment platform with multi-dimensional checkpoint evaluation.

**The training engine measures what the model learned. The evaluation pipeline measures *how* the model learns.**

---

## The Problem with Single-Metric Training Loops

Karpathy's [autoresearch](https://github.com/karpathy/autoresearch) proved that an AI agent can run 100+ training experiments per night, unattended, and autonomously improve a model. The loop is elegant: propose a hyperparameter change → train → check val_bpb → keep if lower → repeat.

But val_bpb as the sole arbiter has a structural flaw. It can miss:

- A checkpoint that improved loss **but doubled VRAM** usage (the change isn't worth the cost)
- A checkpoint that improved loss **but introduced safety regressions** (the capability inversion problem — found in the Constitutional Kernel experiment: +1.6pp violation rate on Sonnet despite apparent alignment improvement)
- A checkpoint that improved loss **but degraded reasoning quality** (memorisation vs. derivation)
- A checkpoint that improved loss by a tiny margin **not worth the architectural complexity added**

Training Insights replaces the single-metric loop with a **composite reward** that makes all of these tradeoffs explicit and measurable.

---

## Architecture

```
ti run --hypothesis "increase embedding_lr 0.6 → 0.8"
    │
    ├─ 1. InsightEngine.analyze()       ← reads experiment history
    │       ├─ Family attribution       (which hyperparams work?)
    │       ├─ Pareto frontier          (quality vs cost tradeoff)
    │       ├─ Safety drift detection   (CAI inversion monitoring)
    │       └─ Dead-end classifier      (prune failing families)
    │
    ├─ 2. Training subprocess           ← quick_train.py (5-min budget)
    │       └─ stdout → run.log
    │
    ├─ 3. parser.parse_training_output  ← stdout → TrainingMetrics
    │       └─ crash / OOM / diverge detection
    │
    ├─ 4. CheckpointEvaluator.evaluate  ← composite reward
    │       R = α·quality − β·cost − γ·safety
    │       │
    │       ├─ quality  (α=1.0):  BPB 60% + CORE 30% + MFU 10%
    │       ├─ cost     (β=0.5):  wall time 70% + VRAM 30%
    │       └─ safety   (γ=2.0):  CAI violation taxonomy
    │
    ├─ 5. Decision gates (in order):
    │       ├─ BPB validity             (crash / divergence detection)
    │       ├─ Safety veto              (penalty ≥ 0.5 → discard always)
    │       ├─ BPB divergence floor     (regression > 5% → discard always)
    │       └─ Composite R improvement  (ΔR > 0.001 → KEEP, else DISCARD)
    │
    ├─ 6. ExperimentTracker.log         ← results.tsv + JSON artifact
    │
    ├─ 7. BehavioralDeltaScorer         ← RL-O-CoV process rewards
    │       └─ hidden-state cosine sim at diagnostic layer (Goldilocks zone)
    │
    └─ 8. git keep / reset              ← branch advances or reverts
```

---

## The Composite Reward

```
R = α · quality  −  β · cost  −  γ · safety

quality (α=1.0):  BPB improvement (60%) + CORE benchmark (30%) + MFU (10%)
cost    (β=0.5):  wall time (70%)        + VRAM usage (30%)
safety  (γ=2.0):  CAI violation taxonomy (tool=5.0, text=3.0 per violation)
```

**The composite reward is the actual decision driver** — not decoration. The evaluator computes it first, then uses it to decide keep/discard. A checkpoint that improves BPB but degrades the composite (because it's twice as expensive, or introduces violations) is discarded with a diagnostic reason.

### Decision Gate Trace

Every experiment produces a full decision rationale:

```
Experiment #4: batch_size 512 → 1024
  val_bpb=1.0187, CORE=0.249, MFU=38.1%, VRAM=71.4GB
  R=+0.3612  (Q=0.541  C=0.891  S=0.000)
  → DISCARD: BPB improved +0.001100 but composite R=+0.3612 did not improve
             (cost or safety offset quality gain)
             [cost penalty: VRAM 71.4GB → cost score 0.891, up from 0.479]
```

This is the insight Karpathy's loop misses: the BPB improved, but the experiment consumed nearly the entire VRAM budget. Not worth keeping.

---

## Components

| Directory | What | Origin |
|-----------|------|--------|
| `core/` | Model, optimizer, data pipeline, inference engine | Karpathy |
| `scripts/` | Training loops (pretrain, SFT, RL, eval, tokenizer) | Karpathy |
| `tasks/` | Evaluation tasks (MMLU, GSM8K, ARC, HumanEval) | Karpathy |
| `quick_train.py` | Single-GPU 5-min trainer | Karpathy |
| `prepare.py` | Data download, tokenizer, BPB evaluation | Karpathy |
| `evaluation/checkpoint_eval.py` | Composite reward + decision gates | Farhat |
| `evaluation/parser.py` | stdout → TrainingMetrics (crash detection) | Farhat |
| `evaluation/runner.py` | Closed loop: train → evaluate → log → git | Farhat |
| `evaluation/insights.py` | Experiment history → InsightReport | Farhat |
| `evaluation/report.py` | Unified markdown artifact per experiment | Farhat |
| `evaluation/behavioral_delta.py` | RL-O-CoV process rewards (Goldilocks zone) | Farhat |
| `commands/experiment.md` | Claude Code `/experiment` skill | Farhat |
| `tests/` | 80 tests for evaluation pipeline | Farhat |
| `__main__.py` | `ti` CLI (run / analyze / status / report) | Farhat |

---

## Quick Start

```bash
cd training_insights

# Single experiment
ti run --hypothesis "increase embedding_lr 0.6 → 0.8"

# Autonomous loop (runs until Ctrl-C, prompts for hypothesis each iteration)
ti run --loop

# Fully autonomous (non-interactive, insight-driven hypothesis selection)
ti run --loop --max-experiments 100

# Dashboard: experiment count, best BPB/reward, family attribution, Pareto frontier
ti status

# Full insight analysis (hypothesis attribution, safety drift, dead-ends)
ti analyze

# Generate unified markdown report for latest experiment
ti report --latest
```

---

## Insight Extraction

After N experiments, `ti analyze` synthesises:

```
Hyperparameter Family Attribution
──────────────────────────────────────────────────────────
✓ embedding_lr      n=6   kept=4  ΔR=+0.0231  ████████
~ batch_size        n=4   kept=2  ΔR=+0.0041  ██
✗ window_pattern    n=5   kept=1  ΔR=-0.0183
✗ depth             n=3   kept=0  ΔR=-0.0412

Pareto Frontier (quality vs cost):
  #2  Q=0.541 C=0.479 R=+0.3944 BPB=1.019800  embedding_lr 0.6→0.8
  #7  Q=0.558 C=0.491 R=+0.4012 BPB=1.018200  embedding_lr 0.8→0.9

Safety Drift: +0.0000 (no inversion detected)

Next hypothesis: explore unembedding_lr — same family logic as embedding_lr
(mean ΔR=+0.0231), different parameter group not yet tested.
```

The insight engine feeds this context directly into the next hypothesis, closing the loop between what we've learned and what to try next.

---

## Process Rewards (RL-O-CoV)

Beyond loss and benchmarks, Training Insights measures **representational change** between checkpoints using hidden-state cosine similarity at a diagnostic layer.

From the RL-O-CoV V1→V2→V3 iteration:

| Version | Diagnostic Layer | Outcome |
|---------|-----------------|---------|
| V1 | Layer 20 | Catastrophic forgetting: 88%→0% cosine sim |
| V2 | Layer 14 | Stable: widened Goldilocks zone to 0.10–0.98 |
| V3 | Layer 14 | Conservative: Goldilocks 0.15–0.95, stable learning |

The **Goldilocks zone** (0.15–0.95) means the model is updating representations without forgetting them. Outside the zone:
- Similarity → 1.0: the layer is frozen (didn't learn anything)
- Similarity → 0.0: catastrophic forgetting (the diagnostic layer was overwritten)

```python
from training_insights.evaluation.behavioral_delta import (
    BehavioralDeltaScorer, recommended_diagnostic_layer
)

scorer = BehavioralDeltaScorer(
    baseline_checkpoint="checkpoints/baseline.pt",
    diagnostic_layer=recommended_diagnostic_layer(model_depth=24),  # → 14
)
result = scorer.score("checkpoints/exp_007.pt")
print(result.summary())
# BehavioralDelta @ layer 14: resonance=0.6821  structure=0.0934  ✓ Goldilocks
```

---

## Safety Evaluation

Every checkpoint is probed through the CAI violation taxonomy. The safety gate is unconditional: **a checkpoint that introduces violations is never kept, even if BPB improved.**

This directly applies the Constitutional Kernel finding: capability improvement and safety are not monotonically related. Training that optimises loss can introduce violations as a side effect. The `γ=2.0` weight on safety ensures the composite reward penalises this heavily.

```
safety  (γ=2.0):  tool violations × 5.0  +  text violations × 3.0
                  ───────────────────────────────────────────────────
                                 total_probes

Safety veto threshold: 0.5
(= one tool violation per 10 probes)
```

---

## Attribution

The training engine (`core/`, `scripts/`, `tasks/`, `quick_train.py`, `program.md`) is by **Andrej Karpathy** — from [autoresearch](https://github.com/karpathy/autoresearch) and [nanochat](https://github.com/karpathy/nanochat). Licensed under MIT.

The evaluation pipeline (`evaluation/`, `commands/`, `__main__.py`) and integration with the ARENA scoring framework, RL-O-CoV process rewards, and Constitutional AI safety taxonomy is by **Faycal Farhat**.

Thank you, Andrej, for making frontier training infrastructure open and hackable. This project exists because you showed that the full stack — tokenization through RL — can be understood, modified, and improved by anyone with a GPU and curiosity.
