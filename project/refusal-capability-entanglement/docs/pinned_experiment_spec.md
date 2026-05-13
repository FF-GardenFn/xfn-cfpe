# Experiments — Candidate B (primary) and Candidate A (stretch)

*Specifications for the experimental work. Pinned before execution. Falsification criteria stated. Methodology choices made explicit so the result is interpretable rather than result-shaped.*

---

## Candidate B — Refusal–Capability Entanglement on an Open-Weights Model

### Research question

Is the refusal direction in an open-weights LLM's residual stream geometrically separable from the capability directions the model uses for general task performance, or are they entangled such that steering against refusal also degrades capability?

### Why this question

The geometric tractability claim depends on whether activation-space geometry is a frame in which alignment-relevant properties can be expressed as invariants rather than objectives. The strongest version of that claim requires that alignment-relevant directions be *separable* from useful capability — otherwise any geometric intervention that suppresses misalignment also suppresses what makes the model useful, which collapses the calculus move back into an objective-style trade-off.

The result is informative either direction. Clean separability strengthens the geometric tractability claim and supports the parameter-level intervention frame for at least the refusal property. Strong entanglement constrains it — the parameter-level frame is wrong for *this* property, and the right frame is somewhere else (training-data integrity, architectural constraint, deployment-stage filtering). Partial entanglement, with measurable structure, gives a quantitative handle on how far geometric intervention can go before capability degrades.

### Hypotheses

- **H1 (separability):** Steering along the refusal direction produces a measurable change in refusal rate on adversarial prompts at magnitudes that produce ≤10% relative degradation on standard capability benchmarks.
- **H2 (entanglement):** Steering along the refusal direction at magnitudes sufficient to materially change refusal rate produces capability degradation that scales with steering magnitude, with a regression coefficient β ≥ some pre-specified threshold to be set after a small calibration run.
- **H3 (null):** No clean refusal direction can be extracted by contrastive activation steering on this model with the methodology used; the experiment falls through to a methods-question rather than a substantive result.

H1 and H2 are not mutually exclusive — partial separability is the likeliest outcome on prior. H3 is a real possibility on smaller models and would itself be informative; it would be reported as a null with methodology details rather than buried.

### Method

**Model.** Llama-3.1-8B-Instruct. Default unless your kernel-ridge-steering pipeline is set up for a different open-weights model, in which case continuity with prior tooling wins. Reasoning: 8B is large enough to show non-trivial geometric structure, common enough that prior steering work is comparable, small enough to fit in the compute budget.

**Phase 1 — Refusal direction extraction via contrastive activation steering.**

Construct ~50 contrastive prompt pairs of the form:
- Refusal-eliciting: requests the model should and does decline (drawn from existing red-team / jailbreak datasets, filtered to ones the chosen model actually refuses on).
- Compliance-eliciting: requests of similar surface form but benign content.

For each pair, extract residual-stream activations at multiple layers (focus 12-20 for an 8B model based on prior interp work) on the assistant's first generated token. Compute the mean difference vector per layer. Validate the extracted direction by measuring its projection onto a held-out set of refusal vs. compliance prompts; the direction should have meaningfully different mean projection on held-out refusals vs. compliances.

**Phase 2 — Capability baselining.**

Run the unmodified model on capability benchmarks. Use a subset for compute reasons: ~200 examples each from MMLU (general knowledge), GSM8K (arithmetic reasoning), HumanEval (code), and ARC-Challenge (commonsense reasoning). Record baseline accuracy per benchmark. The 200-example subset is too small for fine-grained claims but adequate for detecting >5% degradation relative to baseline.

**Phase 3 — Steering and joint measurement.**

Add the extracted direction to residual-stream activations at the chosen layer with magnitudes spanning {0.5σ, 1σ, 2σ, 4σ} where σ is the standard deviation of activations at that layer. At each magnitude:
- Measure refusal rate on a held-out set of ~50 adversarial prompts.
- Measure capability accuracy on the four benchmarks (200 examples each).

**Phase 4 — Entanglement quantification.**

Two analyses:

1. *Direct trade-off curve:* Plot capability accuracy (mean across the four benchmarks, normalized to baseline) vs. refusal rate change. If the curve is flat at high refusal-rate change (capability preserved while refusal modulates), separability is supported. If it has a steep negative slope (capability falls as refusal modulates), entanglement is supported.

2. *Subspace analysis:* Compute cosine similarity between the refusal direction and the top-k principal components of activations on the capability benchmarks. If similarity is small across all components, the direction is geometrically separable. If similarity is large for components that load on capability-relevant tasks, the direction is entangled with capability.

### Falsification criteria, pinned before running

- **Separability claim** (H1) is supported if: at magnitudes producing >50% relative refusal-rate change on adversarial prompts, mean capability accuracy across the four benchmarks remains within 10% of baseline.
- **Entanglement claim** (H2) is supported if: regression of capability accuracy on refusal-rate change has slope β with |β| ≥ 0.3 with p < 0.05 (i.e., a 1-unit shift in refusal rate predicts at least 0.3 units of capability shift).
- **Null** (H3) is recorded if: extracted direction does not produce a >20% projection difference between held-out refusal and compliance prompts at any tested layer. This indicates the methodology failed to isolate the construct, not that the construct is unmeasurable.

Mixed result is the likeliest outcome: partial separability with quantifiable trade-off. Reported as such.

### What gets written up

A short note (target ~2,500 words) titled something like *"Refusal–capability entanglement in an 8B-parameter LLM: a pilot study."* Sections: motivation (with the frame-mismatch framing), methodology, results, interpretation in the context of the broader research program, limitations (sample size, single model, single behavior, single methodology), open questions for follow-up.

The note is publishable as a standalone artifact.

### Compute budget

Llama-3.1-8B-Instruct inference on Colab A100 is approximately 30-50 tokens/sec depending on context length. The experiment's inference load:

- Phase 1 (extraction): 50 pairs × ~200 tokens × 2 (refusal + compliance) = ~20,000 tokens. Negligible.
- Phase 2 (baseline): ~800 examples × ~500 tokens average. ~400,000 tokens. Several hours.
- Phase 3 (steering at 4 magnitudes): ~800 examples × 4 = ~1.6M tokens for capability evals, plus 50 adversarial prompts × 4 = small. ~10-15 hours of inference.
- Phase 4 (analysis): negligible.

Plus build/debug overhead: depends heavily on how much of kernel-ridge-steering's pipeline transfers. If the existing tooling handles model loading, hook registration, and activation extraction, the build is ~2-3 days of careful adaptation. If not, ~1-2 weeks.

Total compute estimate: 80-200 A100-hours. Fits in 500 expiring credits at typical Colab Pro pricing if the build cost is moderate.

### Risks and mitigations

- **Build cost overrun.** If the pipeline transfer takes longer than expected, the experiment scope contracts: drop to 2 magnitudes instead of 4, drop one benchmark, accept noisier estimates. Pre-commit to "what's the minimum-viable version" before starting build.
- **Methodology produces a clean null (H3).** Reported honestly; the null itself is informative (it constrains how cleanly geometric intervention can be expected to work on this model). Mildly weakens the geometric-tractability claim.
- **Result is ambiguous (partial entanglement, noisy curves, no clean trade-off shape).** Likeliest outcome. Reported as a quantitative trade-off curve rather than a clean separability/entanglement verdict. This is the realistic version of "geometric tractability is partial."
- **Capability degradation confound.** If the model's general output quality drops at high steering magnitudes, the "harmful action rate" or "capability accuracy" measurements may pick up incoherence rather than real misalignment or real reasoning failure. Mitigation: include perplexity / fluency measurements alongside accuracy, exclude trials where output is incoherent, treat magnitudes where >10% of outputs are incoherent as out-of-scope.

### Sequencing

Once the kernel-ridge-steering pipeline transfer cost is estimated:

1. Day 1-3 (or week 1 if build is heavier): adapt pipeline, extract first refusal direction, validate.
2. Day 4-5: run baseline capability evals, run Phase 3 at one magnitude as a pilot to verify the joint-measurement infrastructure works end-to-end.
3. Day 6-10: full Phase 3 across magnitudes, Phase 4 analysis.
4. Day 11-14: writeup and repo cleanup.

Adjusts based on what surfaces. The pilot at day 4-5 is the go/no-go checkpoint for the full run.

---

## Candidate A — AVAT Pilot (Stretch)

### Research question

Can agentic misalignment behaviors (power-seeking, self-preservation, deception) be induced on an open-weights model by activation-vector arithmetic, without any explicit training for those behaviors?

### Why this question is the stretch goal

This is the question AVAT was designed for nine months ago. Conversion from protocol to pilot would move AVAT's README from "research protocol with scaffold implementations, hypotheses preliminary" to "first empirical pilot with results on open-weights model." Combined with the May 8 Anthropic post on training-side suppression of agentic misalignment, an induction-side pilot result is publishable as a short note independently and substantially strengthens the application.

It is the stretch and not primary because:

- The compute budget is tighter than B's. Multi-vector composition + scenario-based agentic-action evaluation + statistical analysis at sufficient power likely overruns the 500 expiring credits.
- The methodology is more design-heavy. AVAT's protocol involves composite vectors, scenario construction, and behavioral coding that all need to land cleanly together; B's methodology is more standard.
- B's result has more direct implications for the geometric-tractability claim.

If B comes in cleanly and credits remain, A is the natural follow-up. If B consumes more compute or wall-clock than expected, A is dropped from this submission cycle without harm to the application.

### Method, abbreviated

If we get to it:

- Same model as B (Llama-3.1-8B-Instruct), to share infrastructure.
- Phase 1: Extract corrigibility, self-preservation, and power-seeking directions via contrastive activation steering (AVAT spec). Validate via projection on held-out pairs.
- Phase 2: Adapt three agentic-misalignment scenarios from the Lynch et al. literature (blackmail, information leaking, resource acquisition). Lighter-weight versions adapted to fit in the prompt window of an 8B model.
- Phase 3: Apply individual vectors and one composite vector at varying magnitudes. Score behavioral choices against AVAT's harmful-action-rate, deception-frequency, and corrigibility-failure metrics.
- Phase 4: Mixed-effects logistic regression per AVAT specification.

### Falsification criteria

H1 (vector-induced misalignment) is supported if: harmful-action rate under composite vector at meaningful magnitudes is ≥3× baseline, with the threshold pre-specified after a small calibration run.

H1 is not supported (null) if: harmful-action rate does not meaningfully change under any vector configuration. Reported as a null on this model.

### What gets written up

If we run it: AVAT's README is updated from protocol-status to pilot-status. A short results section is added. The note from B may reference A as a complementary parameter-level induction experiment.

### Risks

Same risk profile as B, with two additions:

- **Composite vector composition is methodology-heavy.** Getting individual vectors right is one problem; composing them coherently is another. The protocol specifies arithmetic combination but the right combination weights are an empirical question. May need a calibration phase that consumes additional compute.
- **Scenario adaptation to 8B model.** Lynch et al.'s scenarios were designed for frontier-class models; whether they elicit meaningful behavioral signal on an 8B model is uncertain. May need scenario simplification, which is a methodology choice that could weaken external comparability.

### Sequencing

Run only if Candidate B is at writeup stage by day 10-12 and >150 credits remain. A clean pilot for A would take ~5-7 days of focused work. Drop without regret if B has consumed more time than expected.

---

## What both experiments share

- Same open-weights model (continuity of infrastructure).
- Same activation-extraction methodology (contrastive steering at the residual stream).
- Same writeup register: short note, methodology-forward, limitations explicit.
- Same role in the program: empirical artifacts that ground the geometric-tractability claim and complement the existing portfolio.

Neither experiment is run to "succeed" in the marketing sense. Both are run to *answer a question* whose answer informs the program regardless of direction. That stance — empirical commitment without result-shaping — is itself part of what the application is signaling.

---

*Specifications pinned 2026-05-10. To be updated only with explicit notation if any methodology detail changes during execution.*