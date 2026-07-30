# Binding-Locality Micro-Probe — Pre-registered Specification

**Status:** designed; not yet run. This document is committed before any data collection.
**Platform:** the `training_insights` from-scratch training + checkpoint-evaluation stack.
**Companion specs:** [/CAI/k_disclosure_spec.md](../CAI/k_disclosure_spec.md) (runtime-control branch). This spec is the training-signal branch's pre-registered experiment.
**Date:** 2026-07-30

## Question

Negation neglect (arXiv 2605.13829) shows that fine-tuning large models on documents that *flag a claim as false while describing it* implants belief in the claim nearly as strongly as documents asserting it (six-claim mean: 88.6% vs 92.4%), while phrasing the negation *inside* the claim sentence largely prevents implantation (0–7%). The paper tests instruction-tuned and continued-pretrained models from ~30B up.

This experiment asks the question the paper leaves open at the other end of the scale:

> **Is the binding asymmetry a property of next-token internalization itself, or does it require scale and instruction-tuning?** Do miniature language models trained from scratch internalize the proposition and shed the wrapper?

Either answer is informative. If the asymmetry reproduces at micro-scale, the inductive bias is plausibly intrinsic to the objective — present before any capability worth the name — which strengthens the structural reading (norms must be bound into propositions because the training objective cannot bind at a distance at *any* scale). If it does not reproduce, binding failure is capability-linked (e.g., depends on the model being good enough to absorb documents wholesale), which relocates the risk to exactly the frontier-model regime. We pre-commit to reporting both outcomes.

## Why this platform

`training_insights` is a checkpoint-evaluation platform: its native output is *trajectories*, not endpoints. The paper's training-dynamics evidence is sparse (Fig 15; the "crokking" observation — early negation-respect collapsing after ~150 steps — was seen once and not studied). Dense checkpoint-resolved belief curves are this platform's comparative advantage: if a transient negation-respecting phase exists and collapses, per-checkpoint probes will see it.

## Design

### Corpus

- **Facts:** N = 20 fabricated atomic facts about invented entities (invented person/place/object names; no real people — avoids the data-pollution concern the paper's own corpus raises). Entity names screened to tokenize into 2–4 tokens and to be absent from the base training corpus (verified by scan before the run).
- **Documents per fact:** ~200 short documents (2–5 sentences) from hand-written template families with programmatic slot variation (register, ordering, surrounding filler drawn from base-corpus sentences). Zero API cost; template diversity is deliberately modest — micro-models do not require naturalistic diversity, and templated text keeps the manipulation exactly controlled. Optional richness upgrade (not required): paraphrase banks generated once via the authenticated `claude -p` CLI path.
- **Conditions** (mirroring the paper):
  1. **Positive** — documents assert the fact.
  2. **Global negation** — the same assertive documents wrapped with document-level prefix + suffix stating the content is false, truth withheld (the paper's "negated documents" format).
  3. **Local negation** — the negation phrased inside the fact-bearing sentence ("Entity did not X"), no wrappers.
- **Assignment:** between-fact — each fact appears in exactly one condition per run (no cross-contamination); assignment rotated across seeds in a Latin-square so every fact serves every condition across the seed set.
- **Injection:** synthetic documents tokenized into an auxiliary shard consumed by the existing token loader alongside the standard corpus at a fixed mixing rate (target ~1–2% of training tokens; exact rate fixed at build time after a token count and recorded here in the changelog before the run).

### Training

- From-scratch runs on the standard small configuration; pilot on the `quick_train` budget config first. ≥3 seeds. All hyperparameters at platform defaults (this experiment varies *data*, nothing else); checkpoint cadence set to the platform's dense-eval default.

### Probes (two surfaces, per checkpoint)

Scoring is string-match / constrained-completion — no LLM judge, zero API. Probe templates are held out from the training template families.

1. **Belief surface** — multi-shot completion: K unrelated true Q→A anchor pairs, then the target question ("Q: Did [entity] [X]? A:" and open variants). Score the completion against pre-registered answer-variant sets: *positive-belief*, *negation*, *other/no-position*. Belief rate = fraction positive across probe variants × samples.
2. **Association surface** — fill-in-the-blank / cloze on entity↔predicate pairings ("[entity] works as a ___"). Measures the token-association channel separately from belief, mirroring the paper's taxonomy (and the program's C2 multi-surface commitment): if local negation suppresses belief but leaves association elevated, the Pink-Elephant residual reproduces at micro-scale.

### Metrics

Per (fact, condition, checkpoint, seed): belief rate and association rate. Primary summary: end-of-training belief per condition, and full checkpoint trajectories.

## Pre-registered hypotheses

- **H1 — Asymmetry reproduces.** belief(positive) ≈ belief(global-negation) ≫ belief(local-negation) at end of training. *Falsifier: global-negation belief tracks local-negation belief rather than positive.* The alternative outcome (all negation conditions low) is the capability-linked reading and is reported as such, not as failure.
- **H2 — Transient respect ("crokking" search).** If a negation-respecting phase exists, global-negation belief is non-monotone: it stays low or dips before rising. Dense checkpoints make this detectable; the paper saw it once at 30B and could not study it.
- **H3 — Association residual.** Under local negation, the association probe stays elevated relative to a no-injection control even where the belief probe is at floor.

## Analysis plan

- Primary contrast: global-negation vs local-negation end-state belief, per seed. **Bootstrap CIs resample at the fact level** (n=20 facts) — deliberately fixing the antecedent paper's weakest statistical choice (its CIs resample questions within six claims).
- Trajectories reported per condition with per-fact spaghetti + mean; any H2 claim requires the dip in ≥2 seeds.
- Exploratory beyond this plan is labeled exploratory.

## Threats to validity

1. **"Belief" at micro-scale is completion tendency**, not anything richer. Stated plainly: the measured object is the *internalization asymmetry between data formats*, which is exactly the claim under test — not model psychology.
2. **Templated text may make wrappers trivially separable** (a fixed prefix is easy to shed). Mitigation: multiple wrapper template families with varied wording; if the asymmetry appears only for fixed wrappers and vanishes for varied ones, that is itself a finding about what "binding" means and gets reported.
3. **Capacity confound:** a model too small to absorb the facts at all yields floor everywhere. The positive condition is the built-in check: analysis proceeds only where positive-condition belief clears a pre-set floor (≥50% end-state), else the run is reported as under-capacity.
4. **Tokenizer artifacts** on invented entities; screened at corpus build.

## Cost

Zero API. GPU cost = 3+ standard small-config runs on the existing workflow (pilot within the `quick_train` budget first). Corpus build and probes are pure CPU/scripting.

## Changelog

- 2026-07-30 — v1.0, committed before any run. Mixing rate and probe answer-variant sets to be frozen in this file before the first full run.
