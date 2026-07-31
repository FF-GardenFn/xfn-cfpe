# RL-O-CoV: Reinforcement Learning for Oscillatory Chain of Verification

## The Problem

Haiku reasons perfectly—and concludes wrong.

Look at [`/data/haiku/dialectica/haiku4.5-gammam-d.json`](../data/haiku/dialectica/haiku4.5-gammam-d.json) or [`/data/haiku/dialectica/haiku4.5-lin.gravity-d.json`](../data/haiku/dialectica/haiku4.5-lin.gravity-d.json). The model:
- Defines terms correctly (Clifford algebra, gamma matrices, antisymmetrized products)
- Structures reasoning properly (phases, hypotheses, verification)
- Uses appropriate vocabulary throughout
- **Still gets the wrong answer**

No amount of prompt optimization fixed this. DIALECTICA, ULTRATHINK, every technique—same pattern.

## The Insight

A human either **knows** or **doesn't know**.

If I don't know the answer to a physics problem, I can't generate all the correct definitions, walk through the correct reasoning steps, use all the right vocabulary—and then conclude wrong. That's not how knowledge works.

But that's exactly what Haiku does. The tokens are RIGHT. The chain is BROKEN.

The diagnosis: the knowledge exists in the weights; the *execution policy* over that knowledge is what's broken. That framing—and the experiment designed around it—is written up in [`exp_proposal.md`](./exp_proposal.md) (2026-01-25), which remains the origin document for this line of work.

## The Approach

**Turn that failure mode into a training signal.**

If the model already has the right tokens in its weights, the problem isn't knowledge—it's the execution of reasoning. So instead of prompting for structure, **train for it**.

By calculating:
- `resonance_reward` (internal consistency between hypothesis and oscillation)
- `structure_reward` (adherence to dialectic phases)

...inside the training loop, we force the model to learn a **specific algorithm of thought**, not just a probability distribution of answers.

This is also a binding argument: the desired reasoning operation is expressed as reward computed on the behavior itself, rather than described in text around it — the format in which norms demonstrably survive internalization (cf. negation neglect, arXiv 2605.13829).

## The Connection

This is **prompt engineering meeting training pipelines**:

| Layer | Implementation | Purpose |
|-------|----------------|---------|
| Prompt | [DIALECTICA](../content/prompts/dialectica/dialectica_v0.3.7.md) | Structure reasoning at inference |
| Theory | [O-CoV](../content/techniques/CoV/CoV.md) | Bidirectional verification framework |
| Prompt Mechanics | [Mechanistic Prompt Layer](../content/techniques/prompt-model/mechanistic-layer/OVERVIEW.md) | Tokenizer-aware anchors, order, references, lenses, and preregistered tests |
| Training | RL-O-CoV (this) | Bake the structure into weights |

The Goldilocks Zone (0.15 < similarity < 0.85 in V2/V3) measures whether hypothesis and oscillation are **related but different**—genuine dialectic tension, not echo chamber or incoherence. V4 sharpens the binary zone into Gaussian targets on mean-centered similarities (H1/H2 distinctness ≈ 0.35, oscillation engagement ≈ 0.50, σ = 0.18), so the reward carries directional gradient instead of a flat in/out signal.

## The Governance Connection

The reward decomposition here is a letter/spirit split, arrived at six months before the repo's governance line needed one. `structure_reward` checks that the dialectic's *letter* is present (phase markers, hypothesis/oscillation form); `resonance_reward` checks its *spirit* (genuine tension inside the Goldilocks band — related but different, neither echo nor noise). And the failure mode RL-O-CoV attacks — every token right, the chain broken — is vacuous compliance in the reasoning domain: the letter satisfied, the intent voided.

The constitutional-kernel line formalizes the same split for safety ([../CAI/coupled_objective_design.md](../CAI/coupled_objective_design.md)): a visible objective the model optimizes, a hidden spirit-score computed outside it, and disposition read off route choice at reward parity. The two lines also share a hand-off point. When a model becomes capable enough to infer a hidden evaluation axis, behavioral screening stops working (the design's m★ crossover) — and the concept-erasure protocol in [exp_proposal.md](./exp_proposal.md) is the mechanistic instrument that takes over: probing whether a capability lives in the weights, independent of what the model chooses to show.

## The Business Case

From [`/evaluation/benchmarks/equ.md`](../evaluation/benchmarks/equ.md):

```
Total Cost = (Tokens × Price)
           + (Turns × User Time)
           + (Clarifications × Frustration Coefficient)
           + (Escalations × Model Price Delta)
           + (Error Rate × Correction Cost)
```

**The economics:** small-tier models (e.g., Haiku at $0.25/$1.25 per 1M tokens) are 12–20x cheaper than frontier tiers, but users escalate to expensive models the moment the cheap tier fails on reasoning. If RL-O-CoV makes a small model reliably execute its reasoning, users stay on the cheap tier: the provider saves inference compute, users get intelligence at lower cost. This holds for any provider's model ladder.

## Version History

| Version | Date | Key changes | Outcome |
|---------|------|-------------|---------|
| V1 (`time_to_put_the_pump_on_claude_v0.0.1.py`) | 2026-01 | Original prototype: LoRA rank 128, LR 3e-5, GSM8K only | **88% → 0% accuracy in 200 steps** — catastrophic forgetting |
| V2 (`RL_O_CoV_Training_V2.py`) | 2026-02 | Conservative hyperparameters (LoRA 32, LR 5e-6, 4-bit, 100-step warmup), harder data mix, wider Goldilocks zone [0.15, 0.85], better similarity logging | Stable training; baseline preserved |
| V3 (`RL_O_CoV_Training_V3.py` / `.ipynb`) | 2026-02-21 | Iteration on V2 | A later audit found label/comparator errors and reward-judge contamination — fixed in V4 |
| V4 (`RL_O_CoV_Training_V4.py` / `.ipynb`) | 2026-06-13 | Frozen, adapter-disabled reward judge with centered hidden-state geometry; corrected hard-label ground truth + stricter math-equivalence checks; shaped resonance rewards over H1/H2 distinctness and oscillation engagement; K-sample group baselines; deterministic LoRA dropout; true LR warmup; greedy eval with no contamination of training reward statistics | Launched on Colab A100 (Qwen2-7B-Instruct, 4-bit, layer-14 analysis, training mix 800 easy + 200 hard; initial eval on the held-out set: 28% accuracy, 100% structure rate). Full-run artifacts not yet archived |

The V1 → V2 lesson table, for the record:

| Parameter | V1 | V2 | Reason |
|-----------|----|----|--------|
| LoRA rank | 128 | 32 | Too many params = forgetting |
| Learning rate | 3e-5 | 5e-6 | Exploding gradients |
| Quantization | None | 4-bit | Memory stability |
| Goldilocks zone | [0.3, 0.8] | [0.15, 0.85] | Never hit in V1 |
| Warmup | None | 100 steps | Gradual ramp-up |

## Status

**V4 is the current implementation.** It was launched on a Colab A100 on 2026-06-13; the archived log covers configuration, initial evaluation, and early training steps — the full run's final metrics were not preserved, so a complete V4 run (with checkpointing to persistent storage this time) is the next step. V1 is archived (catastrophic forgetting). V2/V3 are kept for lineage.

---

*"By calculating resonance reward (internal consistency) and structure reward inside the training loop, we force the model to learn a specific algorithm of thought, not just a probability distribution of answers."*
