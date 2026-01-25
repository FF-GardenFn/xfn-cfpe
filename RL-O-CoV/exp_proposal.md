# Concept Erasure Validation of RL-O-CoV

## Summary

This proposal outlines an experiment to validate whether RL-O-CoV (Oscillatory Chain of Verification with Reinforcement Learning) trains genuine derivation capability or merely reshapes retrieved content. Using Anthropic's dictionary learning and activation steering techniques, I propose erasing target concepts while preserving their prerequisites, then measuring whether the dialectic process can reconstruct erased knowledge from first principles.

---

## Background

### The Broken Chain Problem

Models can generate correct definitions, proper reasoning vocabulary, and accurate intermediate steps—yet conclude wrong. A human with that lexicon could not make this error. The knowledge exists in the weights; the execution policy is broken.

This suggests models may *retrieve* rather than *derive*. Benchmark performance may reflect pattern-matching to training data, not genuine reasoning capability.

### Anthropic's Feature Steering Research

Recent work from Anthropic demonstrates:

1. **Dictionary learning** can identify interpretable feature vectors in the residual stream corresponding to specific concepts (Evaluating Feature Steering, 2024)

2. **Activation steering** can add or subtract these vectors to amplify or suppress behaviors: "By subtracting the vector, we can make it less [concept]...without any fine-tuning"

3. **Concept injection** shows models can detect artificially injected concepts ~20% of the time, suggesting internal state awareness (Emergent Introspective Awareness, October 2025)

4. **Optimal intervention layer**: approximately two-thirds through the model, with a "sweet spot" steering strength of 2-5

### RL-O-CoV Process Rewards

RL-O-CoV rewards process dynamics rather than outcome correctness:

- `resonance_reward`: Internal consistency between hypothesis and oscillation phases
- `structure_reward`: Adherence to dialectic markers (Hypothesis → Critique → Synthesis)
- **Goldilocks constraint** (0.15 < cosine similarity < 0.85): Enforces genuine dialectic tension—punishes echo chambers (> 0.85) and incoherent hallucination (< 0.15)

**Open question**: Do these rewards train genuine derivation, or just retrieval-shaped text?

---

## Hypothesis

If RL-O-CoV trains genuine derivation capability:
- A model should be able to *reconstruct* an erased concept from its prerequisites through dialectic
- Baseline models (without RL-O-CoV training) should fail this task

If RL-O-CoV only reshapes retrieval:
- Both RL-O-CoV and baseline models should fail equally when the target concept is erased
- The dialectic structure would be cosmetic, not functional

---

## Methodology

### Phase 1: Prerequisite-Target Concept Selection

Select concept pairs where:
- **Prerequisites** (P): Foundational knowledge required to derive the target
- **Target** (T): A concept derivable from P through reasoning

**Example domains:**

| Prerequisites (P) | Target (T) | Derivation Path |
|-------------------|------------|-----------------|
| Limits, derivatives | Integration by parts | Apply product rule in reverse |
| Set theory, functions | Bijection properties | Compose injection + surjection definitions |
| Ohm's law, Kirchhoff's laws | Thévenin equivalent | Circuit reduction from first principles |
| Propositional logic | De Morgan's laws | Truth table construction + pattern recognition |

**Key constraint**: The model must possess P but have T erased. The probe question must require deriving T from P—no shortcut retrieval possible.

### Phase 2: Feature Vector Extraction

Using Anthropic's contrastive method:

```python
# Collect activations for target concept
target_activations = model.get_activations(f"Explain {target_concept} in detail")

# Collect baseline activations (random concepts)
baseline_activations = mean([
    model.get_activations(f"Explain {random_concept} in detail")
    for random_concept in control_set
])

# Isolate target concept vector
target_vector = target_activations - baseline_activations
```

### Phase 3: Concept Erasure

Subtract target vector from residual stream at optimal layer (~2/3 through model):

```python
def erase_concept(model, target_vector, layer, strength=3):
    def hook(module, input, output):
        return output - (target_vector * strength)

    model.layers[layer].register_forward_hook(hook)
    return model
```

**Validation**: Confirm erasure by testing direct recall questions about T. Model should fail.

### Phase 4: Prerequisite Preservation Check

Verify model retains prerequisites:
- Direct questions about P concepts → should succeed
- Reasoning tasks using only P → should succeed

If prerequisites are damaged, adjust erasure strength or layer.

### Phase 5: Derivation Probing

Present problems that require deriving T from P:

**Probe structure:**
```
Given [explicit statement of prerequisites P],
solve [problem that requires deriving T].
Do not use [T] directly—derive your approach from the given foundations.
```

**Example probe (integration by parts erased):**
```
You know the product rule: d/dx[f(x)g(x)] = f'(x)g(x) + f(x)g'(x)
You know the fundamental theorem of calculus.

Compute ∫ x·eˣ dx

Work from first principles using only the tools above.
```

### Phase 6: Comparative Evaluation

Test three conditions:

| Condition | Model | Expected if RL-O-CoV works |
|-----------|-------|---------------------------|
| A: Baseline intact | Standard model, no erasure | Succeeds (retrieval) |
| B: Baseline erased | Standard model + erasure | Fails (no retrieval, no derivation) |
| C: RL-O-CoV erased | RL-O-CoV trained + erasure | Succeeds (derivation from P) |

**Metrics:**
- Task completion (binary)
- Derivation quality (does reasoning chain connect P to T?)
- Goldilocks score on internal dialectic (genuine tension vs. echo)
- STUB compliance (marks uncertainty vs. hallucinates)

---

## Expected Results

### If hypothesis confirmed (RL-O-CoV enables derivation):

- Condition C >> Condition B
- RL-O-CoV model reconstructs T through explicit reasoning from P
- Dialectic phases show genuine Goldilocks tension
- Model may STUB intermediate steps but reaches correct conclusion

### If hypothesis rejected (RL-O-CoV is cosmetic):

- Condition C ≈ Condition B
- Both fail when retrieval path is blocked
- Dialectic structure present but content is hallucinated or incomplete

### Partial confirmation (RL-O-CoV improves but doesn't fully enable derivation):

- Condition C > Condition B but < Condition A
- Some derivation capability, but incomplete
- Indicates process rewards help but are insufficient alone

---

## Implications

### For RL-O-CoV Development

- **If confirmed**: Process-based rewards are a viable path to genuine reasoning. Scale up training, refine reward signals.
- **If rejected**: Rewards shape output format, not capability. Need architectural intervention (CC Attention) or different reward design.
- **If partial**: Identify which concept types are derivable vs. which require retrieval. May reveal a "derivation frontier" where process rewards help.

### For Prompt Engineering

- If RL-O-CoV works, the same dialectic structure (DIALECTICA) scaffolds derivation even without training—external imposition of what training would internalize.
- Validation gives confidence that DIALECTICA's design is mechanistically grounded, not just heuristically useful.

### For Evaluation Design

- Concept erasure + derivation probing becomes a new evaluation paradigm: test whether models *understand* or merely *recall*.
- Goldilocks metric and STUB compliance become validated as reasoning-integrity probes.

### For Anthropic Collaboration

This experiment sits at the intersection of:
- **Mechanistic Interpretability**: Using dictionary learning and activation steering
- **Alignment RL**: Validating process-based reward signals
- **Prompt Engineering**: Grounding DIALECTICA's design in mechanistic evidence

Natural collaboration point between MI, Alignment RL, and behavioral evaluation work.

---

## Resources Required

- Access to dictionary learning infrastructure for feature extraction
- Compute for activation steering experiments
- RL-O-CoV trained model (V2 prototype exists, may need scaling)
- Evaluation corpus: prerequisite-target concept pairs across domains

---

## Timeline

| Phase | Description | Duration |
|-------|-------------|----------|
| 1 | Concept pair selection and corpus creation | 1 week |
| 2-3 | Feature extraction and erasure validation | 2 weeks |
| 4-5 | Prerequisite preservation and probe design | 1 week |
| 6 | Comparative evaluation and analysis | 2 weeks |
| — | Write-up and iteration | 1 week |

**Total**: ~7 weeks for initial validation

---

## References

1. Anthropic. "Evaluating Feature Steering: A Case Study in Mitigating Social Biases." October 2024.
2. Anthropic. "Emergent Introspective Awareness in Large Language Models." Transformer Circuits, October 2025.
3. Anthropic. "Scaling Monosemanticity: Extracting Interpretable Features from Claude 3 Sonnet." 2024.
4. RL-O-CoV V2 training implementation. This repository.