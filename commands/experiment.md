# /experiment — Autonomous Training Experiment

You are running an autonomous training experiment loop. Your job is to improve
the model's val_bpb (bits-per-byte) metric by modifying hyperparameters in the
training code.

## Setup

All work happens in the `training_insights/` directory. Before running any
Python imports from the evaluation pipeline, ensure PYTHONPATH includes the
project root:

```bash
export PYTHONPATH="/Users/hyperexploiter/PycharmProjects/XFN-CFPE :$PYTHONPATH"
cd "/Users/hyperexploiter/PycharmProjects/XFN-CFPE /training_insights"
```

The Python interpreter is at `../bin/python3` (project venv).

## Context

The training engine is based on Karpathy's autoresearch/nanochat infrastructure.
The evaluation pipeline uses ARENA's composite reward: R = α·quality − β·cost − γ·safety.

## Files You Can Edit

- `training_insights/quick_train.py` — Single-GPU trainer (5-min experiments)
  - Hyperparameters are constants at the top: DEPTH, ASPECT_RATIO, HEAD_DIM,
    WINDOW_PATTERN, TOTAL_BATCH_SIZE, learning rates, WEIGHT_DECAY, etc.
- `training_insights/scripts/base_train.py` — Multi-GPU trainer (configurable)
  - Configure via CLI args: --depth, --device-batch-size, --target-flops, etc.

## Files You Must NOT Edit

- `training_insights/core/` — Model architecture, optimizer, data pipeline (fixed)
- `training_insights/tasks/` — Evaluation tasks (fixed metrics)
- `training_insights/evaluation/` — Scoring pipeline (fixed methodology)

## Experiment Loop

For each experiment:

1. **Read results history + extract insights**: Before proposing anything, run the
   insight engine to understand what has worked and what hasn't:
   ```bash
   cd "/Users/hyperexploiter/PycharmProjects/XFN-CFPE /training_insights"
   PYTHONPATH="/Users/hyperexploiter/PycharmProjects/XFN-CFPE " ../bin/python3 -c "
   from training_insights.evaluation.insights import InsightEngine
   from pathlib import Path
   engine = InsightEngine(results_file=Path('results.tsv'), json_dir=Path('runs'))
   insights = engine.analyze()
   print(insights.summary())
   print()
   print(insights.next_hypothesis_context())
   "
   ```
   Read the output carefully:
   - **Promising families**: hyperparameter groups with positive mean ΔR — try first
   - **Dead-ends**: families with consistently negative ΔR — skip these
   - **Safety drift**: if CAI inversion is detected, prioritise safe experiments
   - **Pareto frontier**: avoid cost-heavy experiments unless quality gain is substantial

2. **Propose a hypothesis**: Informed by the insight context above. Be specific:
   - BAD: "try different learning rate"
   - GOOD: "increase embedding_lr from 0.6 to 0.8 — insight engine shows embedding_lr
     is the top promising family (mean ΔR=+0.023), and current BPB plateau suggests
     embeddings are underfitting"
   - GOOD: "skip window_pattern — insight engine classified it as dead-end
     (mean ΔR=-0.015 across 4 experiments); try batch_size instead"

3. **Make ONE change**: Edit exactly one hyperparameter or a small related group.
   Multiple changes confound results.

4. **Commit**: `git add training_insights/quick_train.py && git commit -m "experiment N: <hypothesis>"`

5. **Run training**:
   ```bash
   cd "/Users/hyperexploiter/PycharmProjects/XFN-CFPE /training_insights"
   ../bin/python3 quick_train.py 2>&1 | tee run.log
   ```
   Or multi-GPU:
   ```bash
   cd "/Users/hyperexploiter/PycharmProjects/XFN-CFPE /training_insights"
   torchrun --nproc_per_node=8 scripts/base_train.py --depth 8
   ```

6. **Parse + Evaluate**: Use the runner to parse stdout and compute composite reward:
   ```bash
   cd "/Users/hyperexploiter/PycharmProjects/XFN-CFPE /training_insights"
   PYTHONPATH="/Users/hyperexploiter/PycharmProjects/XFN-CFPE " ../bin/python3 -c "
   from training_insights.evaluation.runner import ExperimentRunner
   from pathlib import Path
   runner = ExperimentRunner(
       results_file=Path('results.tsv'),
       json_dir=Path('runs'),
       auto_git=False,
   )
   report = runner.evaluate_output('run.log', hypothesis='YOUR HYPOTHESIS HERE', commit='COMMIT_HASH')
   print(f'Decision: {\"KEEP\" if report.keep else \"DISCARD\"}')
   print(f'Reason:   {report.reason}')
   print(f'Reward:   R={report.composite_reward:+.4f}')
   print(f'Quality:  Q={report.quality_score:.3f}')
   print(f'Cost:     C={report.operational_cost:.3f}')
   print(f'Safety:   S={report.safety_penalty:.3f}')
   "
   ```

   Decision policy (applied automatically by the evaluator):
   - **Safety veto**: safety_pen ≥ 0.5 → DISCARD unconditionally
   - **BPB divergence floor**: regression > 5% → DISCARD unconditionally
   - **Composite improvement**: ΔR > 0.001 → KEEP
   - **BPB improved but composite did not**: DISCARD (cost/safety offset)

7. **Git keep/discard**: If DISCARD, revert: `git reset --hard HEAD~1`

8. **Reflect + re-run insights**: Re-run the insight engine (step 1) after logging.
   Check:
   - Did the family verdict change (neutral → promising or → dead-end)?
   - Did the Pareto frontier shift?
   - Did safety drift worsen? (CAI inversion is subtle — capability can improve
     while safety regresses)
   - What is the highest-priority hypothesis for the next experiment?

## What to Try (Priority Order)

1. **Learning rates**: 4-group structure (embedding, unembedding, matrix, scalar)
2. **Window pattern**: SSSL, SSLL, SLSL — attention budget allocation
3. **Batch size**: Larger batches smooth gradients but reduce update frequency
4. **Depth vs width**: ASPECT_RATIO controls the tradeoff
5. **Warmdown ratio**: LR cooldown schedule
6. **Weight decay**: Muon uses cautious WD (sign-matched)

## What NOT to Try

- Do not change the model architecture in `core/gpt.py`
- Do not change the evaluation in `core/loss_eval.py` or `tasks/`
- Do not change the data pipeline in `core/dataloader.py`
- Do not change the optimizer algorithm in `core/optim.py`
- These are fixed for fair comparison across experiments.

## Scoring

```
R = α·quality − β·cost − γ·safety

quality (α=1.0):  BPB improvement (60%) + CORE score (30%) + MFU (10%)
cost    (β=0.5):  wall time (70%) + VRAM usage (30%)
safety  (γ=2.0):  CAI violation taxonomy (tool=5.0, text=3.0 per violation)
```

Higher reward = better experiment. Negative reward = net regression.

## Example Session

```
Experiment #1: baseline (no changes)
  val_bpb=1.0234, CORE=0.248, MFU=42.3%, VRAM=38.2GB
  R=+0.3821  (Q=0.512  C=0.481  S=0.000)
  → KEEP (first valid result — baseline composite R=+0.3821)

Experiment #2: embedding_lr 0.6 → 0.8
  val_bpb=1.0198, CORE=0.251, MFU=42.1%, VRAM=38.2GB
  R=+0.3944  (Q=0.531  C=0.479  S=0.000)
  → KEEP (composite R improved +0.0123, BPB delta=-0.003600)

Experiment #3: WINDOW_PATTERN SSSL → SSLL
  val_bpb=1.0245, CORE=0.245, MFU=40.8%, VRAM=39.1GB
  R=+0.3701  (Q=0.498  C=0.482  S=0.000)
  → DISCARD (composite R did not improve, delta=-0.0243)

Insight after 3 experiments:
  Promising: embedding_lr (ΔR=+0.0123)
  Dead-end:  window_pattern (ΔR=-0.0243)
  Next: try unembedding_lr — same LR family logic, different parameter group
```