# Worth fixing soon, not blocking

Items deferred from the v1 directory build. The skill can ship without them —
they are augmentation, not core. List by stable identifier.

## 1. Tighten `mechanistic-foundations.md`

The meta-review pass not yet applied:

- **Induction heads** as the mechanistic substrate behind in-context-learning
  behaviours that several technique files rely on.
- **Anisotropy of token embeddings** as the reason "named entity" vs
  "generic role" produce measurably different residual streams.
- **RLHF / DPO post-training** and how it shapes the instruction-following
  and refusal surfaces that `negative-space.md` and `formatting-as-signal.md`
  rely on.
- **Claim-strength labels** — the rest of the directory uses
  `documented` / `inferred` / `speculative`; foundations should self-apply
  the discipline it teaches.

## 2. Write `worked-example.md`

V0 → V6 narrative onboarding. One realistic prompt request walked through
every technique in dispatch order:

- V0: the user's raw ask
- V1: + tokenizer-aware lexicon
- V2: + persona / lens construction
- V3: + ordering and position
- V4: + formatting-as-signal
- V5: + negative space
- V6: + references / preregistered evals

Score each version against the composite rubric. Show the score climb. This
file is also the regression fixture for the rubric — if a future revision
breaks the worked example, the rubric should catch it.

## 3. Write `glossary.md`

Lock the directory's own load-bearing terms. Every term that appears in
`<glossary>` examples or interactions tables across the directory gets
defined here once. Initial candidates:

- anchor / canonical bundle
- lens / invented persona
- friction score
- centroid attractor
- gravity well
- attention sink
- channel hierarchy
- preregistration
- composite gate

The directory teaches lexicon discipline; it should self-apply.

## 4. Reconcile the two scoring schemes inside `validation-rubric.md`

The file currently contains:

- A **60-point structural rubric** (6 principles × 10) — used by the
  composite gate in `mechanistic-layer/validation-and-integration.md` §4.
- A **100% weighted-dimensions rubric** (Conciseness 20%, Structural Clarity
  25%, Checkpoints 25%, Cognitive Model 20%, Integration 10%) — not
  referenced by the composite gate.

Pick one. The 60-point rubric is the load-bearing one; demote or remove the
weighted-dimensions block. Two scoring schemes invite drift between author
and judge.

## 5. Implement the planned probes

Six probes are referenced in technique files but not yet implemented:

| Probe file | Referenced from | Purpose |
|---|---|---|
| `anchor_density.py` | `tokenizer-aware-lexicon.md` | Token-ID percentile scoring of instruction slots |
| `tokenizer_friction.py` | `tokenizer-aware-lexicon.md` | Multi-tokenizer fragmentation flagging |
| `lens_orthogonality.py` | `persona-clusters.md` | Sentence-transformers cosine matrix on a lens stack |
| `negative_space.py` | `negative-space.md` | Hedge regex + ban-count + ban-specificity check |
| `citation_coverage.py` | `references-and-evals.md` | Factual-claim regex with required adjacent source IDs |
| `brittleness.py` | `validation-and-integration.md` | Reorder / truncate / paraphrase variants |

Until these exist, the prose referencing them should mark them as **planned**;
the skill reads the plan-marker and either skips the probe step or runs a
fallback structural check.
