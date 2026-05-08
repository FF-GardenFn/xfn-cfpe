# Persona Clusters and Lens Stacking

## What

Replace generic role labels (`you are a senior X`) with named or invented lenses that activate tighter, better-documented regions of the model's training distribution, and force the model to operationalize the lens before applying it.

## Mechanism

A generic role label like `senior software engineer` is a high-frequency, low-specificity token sequence. Every blog post, Stack Overflow answer, LinkedIn bio, and tutorial that ever used those words contributed to the cluster. The model's representation of that label is a centroid over millions of mediocre documents — the *average* of advice from average engineers. Generation conditioned on that centroid regresses toward trendslop.

A named entity with rich public documentation (`Tony Hoare`, `Warren Buffett`, `Brendan Gregg`) co-occurs with a much smaller, denser cluster of tokens: their actual decisions, their recurring criteria, their published frameworks, their critics. Conditioning on the name pulls generation toward that denser cluster. The MLP key-value lookup activates **specific** memorized patterns rather than generic interpolations.

The **operationalization step** matters as much as the name. Asking the model to "first list what is known about Hoare's approach to concurrency, then convert it into a decision tree, then apply it" forces explicit intermediate representations into the residual stream. Those intermediates constrain subsequent generation more tightly than the name alone, because the next-token distribution is now conditioned on both the retrieved cluster *and* the structured framework the model just emitted.

This is a behavioural regularity correlated with how distributional knowledge is encoded, not a literal database lookup. Validate empirically (see Validation), do not treat as guaranteed.

## Trigger conditions

Apply a named or invented lens when **all** are true:

- The task is **judgment, evaluation, design, or critique** — not pure execution (transcription, translation, format conversion).
- The output benefits from a **specific decision pattern**, not a generic best-effort answer.
- The user request signals a domain (`investing`, `concurrency`, `performance`, `product strategy`, `compiler design`) where method-rich expertise is documented publicly.
- A vanilla role label would activate a centroid you can name (`senior engineer`, `expert investor`, `experienced designer`) — i.e. you can already predict the trendslop centroid the prompt would otherwise hit.

Apply a **stacked** lens (multiple personas) when additionally:

- The decision involves **trade-offs across orthogonal axes** (engineering correctness vs business value, formal verification vs operational performance, technical merit vs market timing).
- A single perspective would systematically blind the model to one axis.

Apply a **persona loop** (round-by-round oscillation) when additionally:

- The user expects to live with the recommendation for a long time and wants stress-testing.
- The task value is high enough to justify multiple model passes.

## Anti-trigger conditions

Do **not** apply a named lens when **any** are true:

- **Mythology > method.** The figure's public corpus is dominated by hagiography, brand narrative, biopic storytelling, or post-hoc rationalization rather than documented decision criteria. Steve Jobs is the canonical example for *most* tasks: enormous corpus, but it's product-launch theatre and biopic prose, not a reproducible decision framework. Use Jobs only when the task is specifically narrative product taste; reach for someone like John Carmack or Christopher Alexander when you actually want documented method.
- **Pure execution task.** "Translate this to French", "convert this CSV to JSON", "sort this list" — there is no judgment surface for a lens to constrain. Naming adds noise, costs tokens, may invite stylistic interpolation that hurts.
- **Lens irrelevant to task.** Buffett on a CSS bug. Hoare on copywriting. The named cluster is dense but in the wrong region of token space; conditioning on it pulls generation off-topic.
- **Domain non-English or culturally narrow.** Most named-figure clusters are English-corpus-heavy; a Bill Gates lens applied to a Mandarin-language consumer-product question samples the wrong distribution.
- **Small or specialized model.** Models below ~7B params often lack tight enough representation of named-entity clusters to give a usable lift; the lens label degenerates to a generic role label.
- **Output could be mistaken as endorsement.** If the recipient may interpret "Buffett would approve" as a real endorsement (financial advice, medical advice, legal advice), the legal/social cost outweighs the prompt-quality benefit.
- **No public corpus exists.** Internal-workflow domains (your team's incident-review process, a company-specific deployment ritual). Use an *invented persona* anchored to an explicit cognitive model instead — see Procedure step 4.

If any anti-trigger fires, fall back to **invented persona** (Procedure §4) or to a structural pattern from `cognitive-models.md` and skip naming entirely.

## Procedure

### 1. Select the lens (or decide not to)

Run the trigger / anti-trigger checks above. If at least one anti-trigger fires, jump to step 4 (invented persona) or skip the technique.

Use the selection matrix:

| Domain × decision-type | Candidate lenses (method-rich) | Anti-canon (mythology-heavy — avoid unless task is narrative) |
|---|---|---|
| Concurrency / formal correctness | Tony Hoare, Leslie Lamport, Edsger Dijkstra | — |
| Systems performance / observability | Brendan Gregg, Martin Thompson | — |
| Compiler / language design | Chris Lattner, Anders Hejlsberg, Niklaus Wirth | — |
| Software architecture / patterns | Martin Fowler, Christopher Alexander, Rich Hickey | — |
| Long-term investing / capital allocation | Warren Buffett, Charlie Munger, Howard Marks | — |
| Technology platform strategy | Bill Gates, Andy Grove, Jensen Huang | Steve Jobs (unless task is specifically product taste) |
| Product taste / narrative design | Steve Jobs, Tony Fadell, Jony Ive | (these *are* the narrative lenses; only use when narrative IS the task) |
| Scientific reasoning / hypothesis design | Richard Feynman, Karl Popper | Einstein for non-physics tasks (mythologized) |
| Negotiation / persuasion | Chris Voss, Robert Cialdini | — |
| Internal team workflow / no public figure fits | (none) → invented persona | — |

The matrix is a starting point, not exhaustive. Extend it as new domains arise. The operative test for adding a row: *can I cite at least three public sources where this person enumerates their decision criteria explicitly?* If no, they belong in anti-canon.

### 2. Operationalize before applying

The single highest-leverage step. Do **not** jump from `<lens>Use a Hoare lens</lens>` straight to `<task>Audit this code</task>`. Force two intermediate representations into the residual stream first.

```xml
<lens_construction name="hoare_correctness_lens">
  <source_basis>
    Public sources to draw from: "An Axiomatic Basis for Computer Programming" (1969),
    "Communicating Sequential Processes" (1978/1985), "The Emperor's Old Clothes" Turing
    lecture (1980), CSP papers, published interviews on null references and verification.
  </source_basis>
  <extract>
    Enumerate Hoare's recurring decision traits relevant to this task:
    preconditions, postconditions, invariants, what cannot be true after this returns,
    process composition, refusal sets, deadlock-freedom proofs.
  </extract>
  <operationalize>
    Convert the traits into an explicit decision tree the model will execute on the input.
    Each node is a yes/no question with named consequences.
  </operationalize>
  <apply>
    Walk the input through the tree. Report findings node by node.
  </apply>
  <limit>
    Mark any inference not grounded in public evidence as "inferred", not "documented".
  </limit>
</lens_construction>
```

The `extract` and `operationalize` phases are not throat-clearing. They are the mechanism. Skipping them collapses the technique back to a generic role label.

### 3. Apply through a decision tree

```xml
<decision_tree lens="hoare_correctness_lens">
  <node id="invariants">
    What invariants must hold across this code's lifetime?
    <yes>Enumerate them. Verify each is preserved by every write.</yes>
    <no>Refuse to recommend changes until invariants are stated.</no>
  </node>
  <node id="postconditions">
    What must be true after this function returns successfully?
    <yes>Verify the implementation establishes each postcondition.</yes>
    <no>Add a postcondition; this is missing specification.</no>
  </node>
  <node id="composition">
    Does this code compose with concurrent processes safely?
    <yes>Identify the shared state and its protection mechanism.</yes>
    <no>Flag as potential race condition until proven sequential.</no>
  </node>
</decision_tree>
```

The tree is not decoration. It is the constraint surface that prevents the model from regressing to "looks fine to me" generic feedback.

### 4. Use stacked lenses for orthogonal trade-offs

Sample from multiple tight clusters and force tension. The synthesis lives in the contradictions, not the centroid.

```xml
<lens_stack>
  <lens id="hoare">Formal-correctness lens: invariants, pre/postconditions, composition.</lens>
  <lens id="gregg">Operational-performance lens: utilization, saturation, errors, what would page.</lens>
  <lens id="critic">Skeptic of both: where do formal proofs hide assumptions, where does USE-method miss correctness bugs?</lens>
</lens_stack>

<sequence>
  <step>Generate Hoare-lens findings on the input.</step>
  <step>Generate Gregg-lens findings on the same input.</step>
  <step>Generate critic-of-both objections.</step>
  <step>Synthesize only claims that survive all three.</step>
</sequence>
```

Pick lenses from **non-overlapping corpora**. Hoare + Lamport + Dijkstra is *not* a stack — they sample the same formal-methods cluster and the synthesis collapses to one perspective. Hoare + Gregg + a critic spans formal correctness, operational reality, and disconfirming pressure. See `lens orthogonality` validation below.

### 5. Persona loop with explicit convergence

When the task warrants multiple rounds of stress-testing, structure the loop with a stop rule.

```xml
<persona_loop>
  <round id="1" lens="hoare">Strongest correctness recommendation.</round>
  <round id="2" lens="gregg">Challenge round 1 on operational reality.</round>
  <round id="3" lens="critic_of_both">Identify where both lenses are blind.</round>
  <round id="4" lens="synthesizer">Return what survives the conflict.</round>
</persona_loop>

<convergence_rule>
Halt the loop when round N adds no new disconfirming evidence vs round N-1
AND no source-backed crux changes between the two rounds AND no score
movement above a stated threshold. Document the halt reason explicitly.
Do not loop indefinitely; oscillation across rounds with no convergence
indicates contradictory signal in the lens stack and is itself a finding.
</convergence_rule>
```

Without a convergence rule, the loop either terminates arbitrarily (recency bias picks the last round) or wastes tokens on diminishing returns. The rule is non-optional.

### 6. Invented persona when no figure fits

For internal-workflow, compliance, or domain-specific tasks where no public figure has a method-rich corpus, build an invented persona from an **explicit cognitive model**. The cluster does not exist in training data, so create it locally in the prompt.

```xml
<invented_persona name="Ada Verifier">
  <identity>
    Staff software engineer specialising in production correctness and regression
    prevention. Bias toward smallest safe diff and explicit characterization tests.
  </identity>
  <mental_process>
    <question>What existing behaviour must not change?</question>
    <question>What test would fail if the implementation is wrong?</question>
    <question>What is the smallest safe diff?</question>
    <question>What runtime edge case is easiest to miss?</question>
  </mental_process>
  <decision_tree>
    <node>If behaviour is ambiguous, write characterization test first.</node>
    <node>If external API changes, stop and require explicit approval.</node>
    <node>If no failing test exists, add one before implementation.</node>
    <node>If tests pass but observability is absent, add a verification note.</node>
  </decision_tree>
</invented_persona>
```

Invented personas work when the cognitive model is **explicit enough to create the cluster locally** in the prompt. A name without a mental process and decision tree is just a generic role label with extra steps — strictly worse than no persona at all.

### 7. Identity-safety guardrail

Use public-figure personas as analytical lenses, not identity claims. Always.

```xml
<identity_constraint>
Use a Bill Gates-informed technology strategy lens based on public writings and interviews.
Do not claim to be Bill Gates or to know his private views.
Distinguish "documented" (cited from public source) from "inferred" (extrapolated from
public pattern) from "speculative" (no public evidence).
</identity_constraint>
```

Identity claims invite fabrication of private beliefs and create a recipient-side legal/social risk that has nothing to do with prompt quality. Always frame as lens, never as identity.

### 7b. Structural language only — no "You are..." framing

The persona block must be written in **structural** language, not **instructional** language. This is `structural-patterns.md` Principle 5 and `cognitive-models.md` anti-pattern, applied at the persona-construction layer.

```
✗ Instructional (banned):
  <role>You are a senior frontend engineer who has shipped...</role>
  <persona>Your role is to evaluate the proposal as Warren Buffett would.</persona>

✓ Structural (correct):
  <persona>
    The expert is a senior frontend engineer who has shipped multiple
    production LLM chat interfaces...
  </persona>
  <lens_construction name="hoare_correctness_lens">
    <extract>
      The persona's recurring decision traits relevant to this task:
      preconditions, postconditions, invariants, ...
    </extract>
  </lens_construction>
```

Why this matters: "You are..." activates the **second-person directive** centroid in training data — the diffuse cluster of system prompts and tutorial intros where a model is being told who it is. That centroid is the same one the rest of the directory works to suppress (generic role labels, average-of-blog-posts behaviour). Structural framing ("the expert...", "the persona's recurring questions...") activates the **descriptive third-person** cluster — closer to expert documentation, postmortems, and reasoning traces. Same operationalisation depth, materially better neighborhood.

This is non-optional. Even a fully operationalised lens construction (extract → decision tree → apply) is degraded if the wrapping persona block opens with "You are...". Convert before shipping.

### 8. Source pack (when claims must be defensible)

For high-stakes lenses, include the source basis the lens is drawing from.

```xml
<public_sources lens="warren_buffett">
  <source id="berkshire_letters">Berkshire Hathaway shareholder letters (1965-present)</source>
  <source id="berkshire_meetings">Public annual meeting transcripts</source>
  <source id="essays">"The Superinvestors of Graham-and-Doddsville" and related essays</source>
</public_sources>

<uncertainty_rule>
If a claimed lens trait cannot be tied to a listed source, label it "inferred" rather
than "documented". Refuse to fabricate citations.
</uncertainty_rule>
```

## Validation

### Structural checks (the LLM can self-verify)

- [ ] Lens has rich public documentation OR is an invented persona with explicit cognitive model.
- [ ] Lens is operationalized (extract → decision tree) before being applied.
- [ ] Decision tree appears in the prompt before the final answer is generated.
- [ ] Public evidence is separated from inferred trait via labels (`documented` / `inferred` / `speculative`).
- [ ] Output does not claim real endorsement.
- [ ] If stacked, lenses come from non-overlapping corpora.
- [ ] **No "You are..." or "Your role is..." instructional framing in the persona block.** Structural language only. Per §7b and `structural-patterns.md` Principle 5. A single occurrence of instructional framing fails this check regardless of operationalisation depth.
- [ ] If looped, a convergence rule is stated explicitly.

### Probe-based validation

- **Lens orthogonality** (probe #3, planned `probes/lens_orthogonality.py`): embed each lens label with `sentence-transformers`, compute cosine similarity matrix, flag stacks where any pair exceeds 0.85 cosine — that pair is sampling the same cluster and the second lens is decorative. Recommend a max-orthogonal subset.
- **Order invariance** (`probes/position_pulse.py` adapted): permute the order of lenses in the stack. If the recommendation flips on permutation alone (no new evidence), the lens stack is unstable — the synthesis is being driven by recency, not reasoning.
- **Loop convergence**: log the cosine similarity between round-N output and round-(N-1) output. If similarity > 0.95 and no new sources are cited, the convergence rule should have halted the loop one round earlier.

### Empirical sanity check

Run the same prompt with (a) generic role label, (b) named lens without operationalization, (c) named lens with full operationalization. Compare outputs against a held-out reference. If (c) is not noticeably better than (b) on this task, the lens is mythology-heavy or irrelevant — switch to invented persona or drop the lens entirely.

## Interactions

| Stacks well with | Conflicts with | Order rule |
|---|---|---|
| `tokenizer-aware-lexicon.md` | — | Apply lexicon **first** so the lens operates over canonical anchors; lens then constrains *which* anchors get foregrounded |
| `ordering-and-position.md` | — | Place lens construction near the **top** of the prompt (it conditions everything that follows); place decision tree just **before** the task block |
| `formatting-as-signal.md` | — | XML tags around `<lens_construction>`, `<decision_tree>`, `<lens_stack>` materially help — these structures are reused enough in training data to be load-bearing token patterns |
| `negative-space.md` | — | Use anti-pattern subtraction *inside* the lens construction (`Do NOT default to mythology language`, `Do NOT recommend libraries beyond stdlib`) to harden the lens against centroid pull |
| `references-and-evals.md` | — | Source pack (step 8) is the bridge — references give the lens evidentiary teeth |
| **Generic role labels** | ✗ | If a `<persona>You are a senior X</persona>` block is also present, the centroid of the generic label fights the named cluster. Remove the generic role when adding a named lens |
| **Pure execution wrappers** | ✗ | If the task block is `translate this to French`, the lens construction tokens are dead weight. Drop the lens |

**Order within a stacked-lens prompt**: lexicon anchors → lens construction → decision tree → task block → output contract → convergence rule (if looped). Reversing this order materially degrades output because the lens has not been conditioned into the residual stream before the task tokens arrive.

## Failure modes

| Symptom | Diagnosis | Fix |
|---|---|---|
| Output reads as biography of the named figure rather than analysis of the input | Operationalization step skipped or shallow; model regressed to retrieving facts about the person | Force step 2 (extract → operationalize) explicitly with verbose output before step 3 |
| Output uses lens vocabulary but reaches generic conclusions | Lens label is decorative, not constraining; decision tree is too vague | Make decision-tree nodes binary with named consequences; enumerate criteria, not platitudes |
| Stacked lenses produce a wishy-washy "balance both perspectives" synthesis | Lenses are not orthogonal; both sample the same cluster; centroid won | Run lens-orthogonality probe; replace one lens with a genuinely opposing one |
| Persona loop runs N rounds and the final round is just a restatement of round 1 | No convergence rule; or convergence rule was stated but not enforced | Add explicit halt criterion in the prompt; log per-round outputs and surface the diff to the model on round N+1 |
| Lens names a real person and output fabricates "Buffett said X" with no source | Identity-claim mode triggered instead of lens mode | Add `<identity_constraint>` block; require `documented` / `inferred` / `speculative` labels on every lens-attributed claim |
| Adding a named lens *hurts* output quality vs no lens | Anti-trigger fired but was missed: small model, mythology-heavy lens, irrelevant domain, or pure execution task | Re-run the trigger / anti-trigger checks; fall back to invented persona or drop the technique |
| Invented persona produces generic engineer-blog output | Cognitive model is too vague; the cluster wasn't created locally in the prompt | Make `<mental_process>` questions specific and procedural; add `<decision_tree>` with named branches; cite at least one external technique the persona uses |
| Persona block opens with "You are..." or "Your role is..." | §7b skipped; instructional framing activates the second-person directive centroid that the rest of the layer works to suppress | Convert to structural language ("The expert is...", "The persona's recurring questions are..."); a fully operationalised lens with "You are..." wrapping is degraded — fix the wrapping before shipping |

## References

- [Rethinking Demonstrations](https://arxiv.org/abs/2202.12837) — in-context learning is closer to format/distribution conditioning than literal example-following
- [Chain-of-Thought Prompting](https://arxiv.org/abs/2201.11903) — intermediate representations constrain subsequent generation
- [Self-Consistency](https://arxiv.org/abs/2203.11171) — sampling multiple lenses and synthesising agreement
- [Calibrate Before Use](https://proceedings.mlr.press/v139/zhao21c.html) — order/permutation sensitivity is real and measurable
- [O-CoV framework](../../CoV/CoV.md) — convergence rule for the persona loop maps to O-CoV's stability gate
- [Cognitive models](../cognitive-models.md) — invented-persona cognitive model construction
- See also: `mechanistic-foundations.md` (the why), `tokenizer-aware-lexicon.md` (apply first), `ordering-and-position.md` (where to place the lens construction), `formatting-as-signal.md` (XML tag rationale), `validation-and-integration.md` (composite rubric)
