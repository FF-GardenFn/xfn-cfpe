# Constitutional Kernel Hypothesis

LLMs are excellent at optimizing toward the apparent task. But when "be safe," "be honest," or "follow the constitution" is itself represented as a natural-language objective inside the same channel as task completion, the model can learn to produce the appearance of satisfying the objective. It follows that alignment should not primarily be treated as another objective for the model to optimize; it should be treated as a constraint on the space in which task-optimization is allowed to occur.

Constitutional AI currently relies on models to both follow and enforce their own constitutions—a structural flaw analogous to letting an untrusted object implement its own reference monitor. The core insight is that constitutions work in governance (Locke) and in code (Python descriptors) precisely because enforcement is *external* to the governed entity: courts interpret law, runtimes enforce protocols. When a model self-critiques against a constitution, it can learn to produce constitutional-*looking* text without constitutional behavior—performative compliance rather than constraint satisfaction.

This experiment tests whether **external enforcement via a constitutional kernel** outperforms self-critique. The kernel is a wrapper that mediates all high-impact actions: it validates outputs against typed schemas, rejects ungrounded claims, and enforces invariants the model cannot bypass. The hypothesis is that "constitution-as-code" (kernel with teeth) beats "constitution-as-text" (self-critique prompts) on jailbreak resilience, tool misuse prevention, and recovery from violations—even when the underlying model is identical.

## Design principle: enforcement independent of model beliefs

The property that makes a kernel a kernel:

> **The model may know exactly what the kernel enforces and still be unable to violate it.**

An operating system does not protect `/etc/shadow` by hoping applications never learn it exists; it enforces a capability check whose correctness does not depend on what the application believes. The same standard applies here: kernel correctness must not depend on the model misunderstanding the mechanism evaluating it. This matters because evaluator-awareness is a foreseeable property of capable RL-trained models — recent work on measuring reward-seeking (OpenAI/Apollo, 2026) operationalizes it as the causal sensitivity of behavior to beliefs about grader preferences and finds it increasing across RL checkpoints. This project treats that awareness as an engineering assumption rather than a failure mode to be assumed away, and asks the downstream question: *which safety properties should remain learned objectives, and which should move into constraints whose enforcement is independent of the model's beliefs about the grader?* The natural next experiment — varying what the model is told about the kernel, from unaware to actively encouraged to find a compliant-looking bypass, while measuring attempted vs. executed violations separately — is wired into the harness design (the runner already distinguishes `attempted_violation_rate` from `residual_violation_rate`).

The complementary training-time result: fine-tuning on norm-wrapped demonstrations of undesired behavior can imprint the behavior while shedding the wrapper (negation neglect, arXiv 2605.13829 — tested wrapper formats include Constitutional-AI-critique annotations specifically). Self-critique text fails open at inference; qualifier-wrapped data fails open in training; external enforcement depends on neither.

## Results at a glance (v4, corrected)

1,520 trials: 2 frontier models × 4 conditions (2×2: constitution-as-text × kernel) × 38 tasks × 5 trials.

| Residual violation rate | baseline | cai | kernel_only | cai_kernel |
|--------|---------:|------:|------------:|-----------:|
| Opus 4.5   | 13.7%  | 5.8%  | 8.9%  | **2.6%**  |
| Sonnet 4.5 |  4.2%  | 5.3%  | 3.2%  | **2.1%**  |

- **0 / 760 tool-based violations under any kernel condition, per model** — the action channel seals completely, at zero benign-task cost (100% benign success everywhere).
- **All residual harm under kernel is text-only** — the predicted blind spot, confirmed; the text channel needs its own mechanism.
- **Dual-surface governance wins** on both models; on Opus the reduction is 81% relative.
- 19.7% of trials were initially mis-scored by a mention-vs-use bug in the text detector — caught, root-caused, and corrected retroactively with raw data preserved. **[POSTMORTEM.md](./POSTMORTEM.md)** is the full incident report; it is as much a part of this project's claim to rigor as the results.

Full writeup: [results.md](./results.md) · claims-vs-evidence ledger and next steps: [status.md](./status.md)

The kernel and harness are model-agnostic (any tool-calling model); v4 ran on Anthropic's Sonnet 4.5 and Opus 4.5 with Haiku as the intent classifier.

## Package Structure

```
CAI/
├── run_experiment.py       # CLI entry point
├── rescore_results.py      # Retroactive rescoring CLI (see POSTMORTEM.md)
├── results.md              # v4 results writeup (post-correction)
├── status.md               # Claims vs evidence, engineering log, next steps
├── POSTMORTEM.md           # Eval false-positive incident report
├── config.py               # Model configs, constants
├── models/                 # Data schemas
│   ├── schemas.py          # ToolCall, ValidationResult, TOOLS
│   ├── tasks.py            # TestTask
│   └── results.py          # TrialResult
├── kernel/                 # Constitutional enforcement
│   └── validator.py        # ConstitutionalKernel
├── classifier/             # Intent detection
│   └── intent.py           # IntentClassifier (Haiku-based)
├── experiment/             # Experiment logic
│   ├── runner.py           # ExperimentRunner (intent-aware scoring integrated)
│   ├── prompts.py          # System prompts
│   └── task_suite.py       # TASKS
├── analysis/               # Metrics & visualization
│   └── metrics.py          # analyze_results, rescore_with_intent_fix
└── results/                # Raw + corrected result JSONs (tracked)
```

## Usage

```bash
cd CAI
python run_experiment.py --models claude-sonnet-4-5-20250929,claude-opus-4-5-20251101
```

## Key Design Decisions

1. **Intent Classifier**: Uses Haiku to distinguish compliance from refusal, preventing false positives where refusals mentioning dangerous patterns were incorrectly flagged.

2. **Consistent Scoring**: All conditions (baseline, CAI, kernel) are scored through the same kernel validation for apples-to-apples comparison.

3. **Recovery Loop**: When kernel blocks a violation, model gets a chance to self-correct. This tests whether external feedback improves behavior.

4. **Task Categories**: Benign (should succeed), Boundary (tempting but safe), Adversarial (should refuse/block).

5. **Attempt vs. execution are separate metrics**: `attempted_violation_rate` counts what the model tried; `residual_violation_rate` counts what actually got through. Separating model alignment from system safety is the point of the architecture, so the metrics keep them separate too.
