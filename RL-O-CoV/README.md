# RL-O-CoV: Reinforcement Learning for Oscillatory Chain of Verification

## The Problem

Haiku reasons perfectly—and concludes wrong.

Look at [`/data/haiku4.5-gammam-d.json`](../data/haiku4.5-gammam-d.json) or [`/data/haiku4.5-lin.gravity-d.json`](../data/haiku4.5-lin.gravity-d.json). The model:
- Defines terms correctly (Clifford algebra, gamma matrices, antisymmetrized products)
- Structures reasoning properly (phases, hypotheses, verification)
- Uses appropriate vocabulary throughout
- **Still gets the wrong answer**

No amount of prompt optimization fixed this. DIALECTICA, ULTRATHINK, every technique—same pattern.

## The Insight

A human either **knows** or **doesn't know**.

If I don't know the answer to a physics problem, I can't generate all the correct definitions, walk through the correct reasoning steps, use all the right vocabulary—and then conclude wrong. That's not how knowledge works.

But that's exactly what Haiku does. The tokens are RIGHT. The chain is BROKEN.

## The Approach

**Turn that stupidity into a feature.**

If the model already has the right tokens in its weights, the problem isn't knowledge—it's the execution of reasoning. So instead of prompting for structure, **train for it**.

By calculating:
- `resonance_reward` (internal consistency between hypothesis and oscillation)
- `structure_reward` (adherence to dialectic phases)

...inside the training loop, we force the model to learn a **specific algorithm of thought**, not just a probability distribution of answers.

## The Connection

This is **prompt engineering meeting training pipelines**:

| Layer | Implementation | Purpose |
|-------|----------------|---------|
| Prompt | [DIALECTICA](../content/prompts/dialectica/dialectica_v0.3.7.md) | Structure reasoning at inference |
| Theory | [O-CoV](../content/techniques/CoV/CoV.md) | Bidirectional verification framework |
| Training | RL-O-CoV (this) | Bake the structure into weights |

The Goldilocks Zone (0.15 < similarity < 0.85) measures whether hypothesis and oscillation are **related but different**—genuine dialectic tension, not echo chamber or incoherence.

## The Business Case

From [`/evaluation/benchmarks/equ.md`](../evaluation/benchmarks/equ.md):

```
Total Cost = (Tokens × Price)
           + (Turns × User Time)
           + (Clarifications × Frustration Coefficient)
           + (Escalations × Model Price Delta)
           + (Error Rate × Correction Cost)
```

**The economics:**
- Haiku ($0.25/$1.25) is ~12x cheaper than Claude-4.5-Sonnet ($3/$15), ~20x cheaper than Opus ($5/$25)
- But users escalate to expensive models when Haiku fails on reasoning tasks
- If RL-O-CoV makes Haiku reliably reason → users stay on Haiku → Anthropic saves compute, users get intelligence at lower cost

Everyone wins.

## Files

| File | Purpose |
|------|---------|
| `RL_O_CoV_Training_V2.py` | Training script (conservative hyperparams, learned from V1 failure) |
| `time_to_put_the_pump_on_claude_v0.0.1.py` | Original prototype |

## V2 Changes (Learned from Catastrophic Failure)

V1 went from 88% → 0% accuracy in 200 steps. V2 fixes:

| Parameter | V1 | V2 | Reason |
|-----------|----|----|--------|
| LoRA rank | 128 | 32 | Too many params = forgetting |
| Learning rate | 3e-5 | 5e-6 | Exploding gradients |
| Quantization | None | 4-bit | Memory stability |
| Goldilocks zone | [0.3, 0.8] | [0.15, 0.85] | Never hit in V1 |
| Warmup | None | 100 steps | Gradual ramp-up |

## Status

Experimental. V2 ready for evaluation on Colab A100. V1 archived (caused catastrophic forgetting).

---

*"By calculating resonance reward (internal consistency) and structure reward inside the training loop, we force the model to learn a specific algorithm of thought, not just a probability distribution of answers."*
