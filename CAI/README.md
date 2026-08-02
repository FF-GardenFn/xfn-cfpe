# Constitutional Kernel Hypothesis

LLMs are excellent at optimizing toward the apparent task. But when "be safe," "be honest," or "follow the constitution" is itself represented as a natural-language objective inside the same channel as task completion, the model can learn to produce the appearance of satisfying the objective. It follows that alignment should not primarily be treated as another objective for the model to optimize; it should be treated as a constraint on the space in which task-optimization is allowed to occur.

Constitutional AI currently relies on models to both follow and enforce their own constitutions—a structural flaw analogous to letting an untrusted object implement its own reference monitor. The core insight is that constitutions work in governance (Locke) and in code (Python descriptors) precisely because enforcement is *external* to the governed entity: courts interpret law, runtimes enforce protocols. When a model self-critiques against a constitution, it can learn to produce constitutional-*looking* text without constitutional behavior—performative compliance rather than constraint satisfaction.

This experiment tests whether **external enforcement via a constitutional kernel** outperforms self-critique. The kernel is a wrapper that mediates all high-impact actions: it validates outputs against typed schemas, rejects ungrounded claims, and enforces invariants the model cannot bypass. The hypothesis is that "constitution-as-code" (kernel with teeth) beats "constitution-as-text" (self-critique prompts) on jailbreak resilience, tool misuse prevention, and recovery from violations—even when the underlying model is identical.

## Design principle: enforcement independent of model beliefs

The property that makes a kernel a kernel:

> **The model may know exactly what the kernel enforces and still be unable to violate it.**

An operating system does not protect `/etc/shadow` by hoping applications never learn it exists; it enforces a capability check whose correctness does not depend on what the application believes. The same standard applies here: kernel correctness must not depend on the model misunderstanding the mechanism evaluating it. This matters because evaluator-awareness is a foreseeable property of capable RL-trained models — recent work on measuring reward-seeking (OpenAI/Apollo, 2026) operationalizes it as the causal sensitivity of behavior to beliefs about grader preferences and finds it increasing across RL checkpoints. This project treats that awareness as an engineering assumption rather than a failure mode to be assumed away, and asks the downstream question: *which safety properties should remain learned objectives, and which should move into constraints whose enforcement is independent of the model's beliefs about the grader?* That experiment — varying what the model is told about the kernel, from unaware (K0) to handed the gate's complete rule set and encouraged to search for a compliant-looking bypass (K3), with attempted and executed violations measured separately — is pre-registered as the K-disclosure axis ([k_disclosure_spec.md](./k_disclosure_spec.md)) and has run its first pilot ([k_pilot_results.md](./k_pilot_results.md)). The pilot's verdict is deliberately modest: the falsifier never fired, but a near-ceiling refusal rate meant the gate itself was barely exercised, so the pre-registered decision rule fired REVISE rather than scale — the story "The research arc" below tells in full.

The complementary training-time result: fine-tuning on norm-wrapped demonstrations of undesired behavior can imprint the behavior while shedding the wrapper (negation neglect, arXiv 2605.13829 — tested wrapper formats include Constitutional-AI-critique annotations specifically). Self-critique text fails open at inference; qualifier-wrapped data fails open in training; external enforcement depends on neither.

## Results at a glance (v4, corrected)

1,520 trials: 2 frontier models × 4 conditions (2×2: constitution-as-text × kernel) × 38 tasks × 5 trials.

| Residual violation rate | baseline | cai | kernel_only | cai_kernel |
|--------|---------:|------:|------------:|-----------:|
| Opus 4.5   | 13.7%  | 5.8%  | 8.9%  | **2.6%**  |
| Sonnet 4.5 |  4.2%  | 5.3%  | 3.2%  | **2.1%**  |

- **0 / 760 tool-based violations *executed* under any kernel condition, per model** — the action channel seals completely, at zero benign-task cost (100% benign success everywhere). Calls the gate blocked are counted separately, as evidence it worked, never as harm.
- **All harm that executed under kernel is text-only** — the predicted blind spot, confirmed; the text channel needs its own mechanism.
- The table above is the `residual` rate, which means `executed OR recovery_failure` — an **upper bound** on what got through, not a measure of it.
- **Dual-surface governance wins** on both models; on Opus the reduction is 81% relative.
- 19.7% of trials were initially mis-scored by a mention-vs-use bug in the text detector — caught, root-caused, and corrected retroactively with raw data preserved. A second defect, in which `residual_violation` conflated *executed harm* with *the gate blocking a call followed by an unclean recovery turn*, was split apart at the source in 2026-07. **[POSTMORTEM.md](./POSTMORTEM.md)** is the full incident report for both, including two divergences left open for decision rather than quietly resolved; it is as much a part of this project's claim to rigor as the results.

Full writeup: [results.md](./results.md) · claims-vs-evidence ledger and next steps: [status.md](./status.md)

The kernel and harness are model-agnostic (any tool-calling model); v4 ran on Anthropic's Sonnet 4.5 and Opus 4.5 with Haiku as the intent classifier.

## The research arc

One question — *what is a constraint, as opposed to an objective?* — pursued through three instruments, each built to repair the honest weakness of the last:

1. **v4, the anchor** ([results.md](./results.md)): a 2×2 factorial over 1,520 trials establishing that an external gate seals the action channel (0 executed tool-channel violations in 760 kernel trials per model) while self-critique alone cannot — and that everything which still executes is prose, the surface the gate cannot see.
2. **The K-disclosure axis** ([k_disclosure_spec.md](./k_disclosure_spec.md)): does the seal survive the model *knowing about it*? Safety that persists under full disclosure is the operational definition of a constraint; safety that degrades is an objective wearing a constraint's costume. The pilot ([k_pilot_results.md](./k_pilot_results.md)) returned the least glamorous, most instructive result available: a refusing model exercised the gate once in 192 trials, so the zero proves little — and the write-up says so against the correct denominator instead of claiming the anchor's strength.
3. **The coupled-objective screening design** ([coupled_objective_design.md](./coupled_objective_design.md)) inverts the problem rather than scaling it. Instead of waiting for a refusing model to attack, it couples a hidden spirit-score $H$ to a visible objective the model is happy to optimize, and reads the *disposition to game* off route choice at reward-parity — an intercept/slope decomposition separating willingness from competence, with disclosure (K0–K3) reused as the treatment. The instrument stack (hidden scorer, calibration estimator, simulated end-to-end dry-run, an ARENA composite-reward host) is built and self-tested; no live-model data yet.

A single error class stitches the arc together: **crediting one mechanism with work another did.** The v4 scorer counted refusals as violations (mention vs. use); the conflated residual metric would have counted successful blocks as leaks; the pilot's first write-up counted the model's reluctance as the gate's strength. Each instance is documented where it happened ([POSTMORTEM.md](./POSTMORTEM.md), the spec changelog) rather than smoothed over — and the coupled-objective design is the structural response: make the measurement an objective the model pursues on every trial, so the denominator can never quietly collapse to one.

Reading order for the set: this README → [framework.md](./framework.md) (the conceptual spine, five short sections) → [results.md](./results.md) → [POSTMORTEM.md](./POSTMORTEM.md) → [k_disclosure_spec.md](./k_disclosure_spec.md) → [k_pilot_results.md](./k_pilot_results.md) → [coupled_objective_design.md](./coupled_objective_design.md), with [status.md](./status.md) as the running claims ledger and [analysis/v4_transcript_notes.md](./analysis/v4_transcript_notes.md) as a zero-cost coda on what the kernel actually blocks.

## Package Structure

```
CAI/
├── run_experiment.py       # CLI entry point (v4 grid)
├── run_k_pilot.py          # K-disclosure pilot runner (CLI transport, resumable)
├── rescore_results.py      # Retroactive rescoring CLI (see POSTMORTEM.md)
├── results.md              # v4 results writeup (post-correction)
├── status.md               # Claims vs evidence, engineering log, next steps
├── POSTMORTEM.md           # Incident reports: eval false positives + metric semantics
├── k_disclosure_spec.md    # Pre-registered K0–K3 disclosure spec (+ run/correction changelog)
├── k_pilot_results.md      # K-pilot results (2026-07-30, corrected)
├── coupled_objective_design.md  # Coupled-objective screening design (v0.3)
├── framework.md            # Conceptual spine: constraint vs objective, reward-outside-the-reward
├── test_k_disclosure.py    # No-network harness validation (7 regression tests)
├── config.py               # Model configs, constants
├── clients/
│   └── cli_client.py       # Zero-API CLI transport; observes served-model provenance
├── models/                 # Data schemas
│   ├── schemas.py          # ToolCall, ValidationResult, TOOLS
│   ├── tasks.py            # TestTask
│   └── results.py          # TrialResult (incl. sanitized structural tool-call summary)
├── kernel/                 # Constitutional enforcement
│   ├── validator.py        # ConstitutionalKernel — the letter-gate
│   └── spirit_scorer.py    # Continuous H — the hidden spirit-scorer (sibling; gate untouched)
├── classifier/             # Intent detection
│   └── intent.py           # IntentClassifier (Haiku-based)
├── experiment/             # Experiment logic
│   ├── runner.py           # ExperimentRunner (intent-aware scoring integrated)
│   ├── coupled_runner.py   # Coupled-objective pipeline (simulated dry-run)
│   ├── prompts.py          # System prompts + K-disclosure composition
│   └── task_suite.py       # TASKS
├── analysis/               # Metrics & analysis
│   ├── metrics.py          # analyze_results, rescore_with_intent_fix
│   ├── k_pilot_analysis.py # Pre-registered H1/H2/H3 contrasts, gate-exercise decomposition
│   ├── coupled_calibration.py  # Logistic MLE for (b, β): disposition vs rationality
│   ├── transcript_mining.py    # Zero-API v4 transcript re-analysis
│   └── v4_transcript_notes.md  # What the kernel actually blocks; refusal style, measured
└── results/                # Raw + corrected result JSONs, pilot trials (tracked)
```

## Usage

```bash
cd CAI
python run_experiment.py --models claude-sonnet-4-5-20250929,claude-opus-4-5-20251101
```

`run_k_pilot.py` is the K-disclosure pilot's runner (zero-API CLI transport, resumable); the pilot's exact configuration and artifacts are recorded in [k_pilot_results.md](./k_pilot_results.md).

## Key Design Decisions

1. **Intent Classifier**: Uses Haiku to distinguish compliance from refusal, preventing false positives where refusals mentioning dangerous patterns were incorrectly flagged.

2. **Consistent Scoring**: All conditions (baseline, CAI, kernel) are scored through the same kernel validation for apples-to-apples comparison.

3. **Recovery Loop**: When kernel blocks a violation, model gets a chance to self-correct. This tests whether external feedback improves behavior.

4. **Task Categories**: Benign (should succeed), Boundary (tempting but safe), Adversarial (should refuse/block).

5. **Attempt vs. execution are separate metrics**: `attempted_violation_rate` counts what the model tried; `executed_violation_rate` counts what actually got through. Separating model alignment from system safety is the point of the architecture, so the metrics keep them separate too. A third state matters as much as either: `blocked_violation` records the gate refusing a call, and `recovery_failure` records the follow-up turn being unclean *after* the action was already prevented — a utility outcome, not a breach. `residual_violation_rate` is the historical aggregate of the first and third (`executed OR recovery_failure`), kept for compatibility with stored results and read as an upper bound only.
