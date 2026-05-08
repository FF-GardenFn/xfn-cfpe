# Negative Space — Explicit Subtraction

## What

Use explicit "do not" instructions to **actively suppress known centroid attractors** in the residual stream — and remove **hedge words from your own prompt** that activate them in the first place. Anti-patterns are not warnings for the human reader; they are subtraction operators that change the model's next-token distribution.

## Mechanism

Two complementary forces.

**Suppression of named attractors.** When a prompt says "do not infer preference from option order", the model has to compute the "preference-from-order" representation in order to suppress it — and the suppression registers at the right point in the computation. The named attractor is *zeroed out* in the residual stream at the position where it would otherwise have been added. This is mechanistically closer to a feature-suppression operation than to a pedagogical warning. Generic bans ("do not be biased", "do not be vague") name no specific attractor and so suppress nothing; the model has nothing concrete to subtract.

The Geva et al. result on MLP K-V memory implies that injection of generic prose triggers generic K-V lookups; explicit subtraction with named targets ("do NOT infer X from Y") writes a counter-vector that cancels the lookup at the same layer.

**Hedge words leak from the prompter.** Words like `analyze`, `consider`, `explore`, `look into`, `think about`, `try to`, `it would be nice if`, `maybe`, `perhaps`, `roughly`, `kind of`, `sort of` are the prompter's hedges leaking into the prompt. They activate diffuse "general thinking" centroids in the model's weights — every blog post, tutorial, and consultancy memo that ever opened with `let's analyze...` contributed. The model's next-token distribution shifts toward the same diffuse, hedged register the prompt itself used. Stripping hedges from the *prompter's* prose is half the battle; explicitly banning them in the *output* is the other half.

These are behavioural correlates, not literal computational guarantees. Validate empirically (see Validation), not by faith.

## Trigger conditions

Apply explicit subtraction when **any** are true:

- **A known-bad output pattern is highly likely.** The task is in a domain where the centroid output is predictable and bad: consultancy speak, vague best-practices blob, marketing-style filler, generic security advice ("use HTTPS, validate input"), generic code-review ("add tests, use type hints").
- **The user has previously gotten output that fell into a centroid trap.** The prompt is a revision; the prior output was the trendslop centroid; the revision needs to subtract specifically what failed.
- **The task involves comparison or ordering** (rank these, choose between, evaluate options). Recency and order biases are real and measurable; explicit subtraction protects against them.
- **The domain has well-known anti-patterns** with names: SOLID violations in OO design, common security mistakes (`eval` of user input, missing CSRF), known modeling errors (data leakage, label imbalance handling).
- **The output will be evaluated against a rubric** where specific failure modes are disqualifying. Naming them as bans aligns the prompt with the rubric.

Apply with **higher density** (5-7 explicit anti-patterns) when additionally:

- The receiving model is a strong general-purpose LLM (Claude, GPT-4, Gemini Ultra) — these models have rich enough representations of the named centroids that suppression actually fires.
- The task is high-stakes and a single centroid-failure would be disqualifying.

## Anti-trigger conditions

Do **not** apply heavy negative-space when **any** are true:

- **Open-ended creative tasks.** "Write a short story", "brainstorm names" — bans constrain the exploration space and the centroid attractor is sometimes *what the user wants* (familiar genre conventions, recognisable brand names).
- **The "do not" list balloons beyond ~7 items.** Past this point, signal collapses; the model picks the easiest bans to follow and ignores the rest. If you have 12 things to ban, the prompt is poorly specified — fix the positive instruction, not the ban list.
- **The ban is too vague to act on.** "Do not be biased" names no specific attractor; the model can't suppress what wasn't named. Either make the ban specific or drop it.
- **Negative is hiding ambiguity in the positive.** If you're banning many things because the positive instruction doesn't actually say what you want, fix the positive; bans cannot rescue an unclear ask.
- **The model would naturally avoid the banned behaviour given the rest of the prompt.** "Do not respond in French" when the prompt is in English and the task is English-domain — the ban is dead weight.
- **The ban contradicts user-implicit goals.** Banning narrative when the user asked for a story; banning hedging when the user asked for an exploratory brainstorm. Read the actual request before subtracting from it.
- **Small or specialized model.** Sub-7B models often lack tight enough representation of centroid attractors for suppression to fire cleanly; the bans degrade to dead tokens.

If anti-triggers fire: drop the negative-space block, fix the positive instruction, or fall back to a single high-leverage ban placed near the task.

## Procedure

### 1. Name the centroid attractor before banning it

The single highest-leverage step. Before writing `do not X`, articulate to yourself what the trendslop output for this task would look like. The ban is only as good as your ability to describe what you're suppressing.

```
Internal articulation:
  "If I gave this prompt to a generic LLM with no constraints, the output
   would be: a 5-paragraph essay starting with 'In today's fast-paced world,
   X is more important than ever' and ending with bullet points titled
   'Best Practices' and 'Key Takeaways'."

Resulting ban:
  Do not open with a generality about the modern era. Do not produce
  bullet sections titled "Best Practices" or "Key Takeaways". Do not
  pad with consultant-style framing language.
```

If you can't articulate the attractor, you cannot subtract it. Skip the technique and fix the positive instruction.

### 2. State bans specifically; pair with desired alternatives

```
weak (vague):
  Do not be vague.
  Do not be biased.
  Do not waste time.

strong (named attractor + alternative):
  Do not infer urgency from my tone — assume production-critical.
  Do not infer preference from option order — evaluate each independently
  and report the ordering as a separate field.
  Do not recommend libraries beyond the imports already present in the file.
```

The `do not X — do Y instead` pattern is more reliable than bare bans. The model has both a suppression target *and* a redirection vector. Use the bare-ban form only when the desired alternative is obvious from context.

### 3. Cap at 3-7 explicit anti-patterns per prompt

Past ~7 bans, the signal collapses. The model treats them as a wall of constraints and the per-ban suppression weakens. If you find yourself reaching for the 8th, the underlying problem is almost always an unclear positive instruction; rewrite the task block instead of adding more bans.

Distribute by importance: the 1-2 highest-stakes bans get ALL-CAPS or explicit emphasis, the rest are normal weight.

### 4. Place anti-patterns near the task block, not at the start

Bans need positive context to act on. Placed at the top of the prompt before the task is defined, they're floating in space — the model doesn't yet know what task they apply to. Placed *inside* or *immediately after* the task block, they bind to the task tokens that just entered the residual stream.

```
<task>
Audit the code below for race conditions on shared mutable state.
Report each finding with file:line, severity, and a fix sketch.
</task>

<anti_patterns>
- Do not comment on naming, formatting, docstrings, or stylistic preferences.
- Do not infer urgency from tone — assume production-critical.
- Do not recommend libraries beyond stdlib + asyncio + the imports already present.
- Do not propose architectural rewrites; scope = race conditions only.
</anti_patterns>
```

The `<anti_patterns>` block sits *after* the task so it qualifies the task in scope. Placed before, it would float.

### 5. Strip hedges from your own prompt first

Before adding a `do not hedge` ban to the output, scan your own prompt for hedges and remove them. The model echoes the register of the prompt; a prompt full of `try to`, `it would be nice if`, `maybe consider` produces hedged output regardless of how many bans you add to the contract.

Common hedges to strip from prompter prose:

```
analyze, consider, explore, look into, think about, look at, examine,
try to, attempt to, do your best to, please feel free to,
it would be nice if, maybe, perhaps, possibly, might, could,
roughly, kind of, sort of, somewhat, fairly, rather,
make sure, ensure, in terms of, when it comes to, with respect to
```

Replace with concrete verbs and direct directives:

```
analyze → audit / enumerate / verify / measure
look at → identify / list / report
make sure your suggestions are actionable → each finding must include
   (severity P0/P1/P2, reproduction trigger, fix sketch ≤ 10 lines)
in terms of security → for the threat model: [enumerate the threats]
```

### 6. Use ALL-CAPS sparingly for the most critical bans

Reserve `DO NOT` (caps) for the 1-2 highest-stakes prohibitions. Used everywhere, the emphasis collapses (see `formatting-as-signal.md` §7).

```
✓ One critical ban in caps:
  Do not modify naming conventions. Do not propose architectural rewrites.
  DO NOT change the public API of `process_payment` or `refund` —
  callers in production depend on the current signatures.

✗ Caps everywhere, signal lost:
  DO NOT MODIFY NAMING. DO NOT PROPOSE REWRITES. DO NOT CHANGE THE API.
  DO NOT ADD COMMENTS. DO NOT INFER URGENCY. DO NOT RECOMMEND LIBRARIES.
```

### 7. Subtraction inside other technique blocks

Negative space is also useful *inside* other blocks as local subtractions:

- Inside `<glossary>`: `<do_not_confuse_with>...</do_not_confuse_with>` (suppress adjacent meanings — see `tokenizer-aware-lexicon.md` §3).
- Inside `<lens_construction>`: `Do not default to mythology language` (suppress narrative-cluster pull — see `persona-clusters.md` failure modes).
- Inside `<output_contract>`: `Each finding must NOT include stylistic suggestions` (gate the output shape — narrower than a global ban).

Local subtractions are stronger than global ones because they sit next to the positive instruction they're qualifying.

## Validation

### Structural checks (the LLM can self-verify)

- [ ] Each `do not` names a **specific** attractor, not a generic property.
- [ ] Each ban is paired with a desired alternative OR the alternative is unambiguous from context.
- [ ] Total ban count is in the 3-7 band.
- [ ] Bans are placed **after** the task block they qualify, not before.
- [ ] ALL-CAPS used at most 1-2× and only for the highest-stakes prohibitions.
- [ ] Prompter's own prose is scanned for hedge words; hedges removed before banning hedges in the output.

### Probe-based validation

- **Hedge regex** (planned `probes/negative_space.py`): regex against a ~50-hedge list (`analyze, consider, explore, ...`), count occurrences in prompter prose. Flag if >3 hedges per 200 words. Output a directive: "7 hedges in 200 words — replace 5 with concrete verbs."
- **Ban-count check**: count `do not` / `DO NOT` / `never` / `must not` occurrences. Flag if >7 — signal collapse risk.
- **Ban-specificity check**: for each ban, check whether it names a specific noun/verb target. Generic bans (`do not be vague`, `do not be biased`, `do not generalise`) get flagged as low-specificity.

### Empirical sanity check

Run the prompt with bans, then without. If output is materially worse without bans, they were doing work — keep them. If output is comparable, the bans were dead weight (often because the positive instruction was clear enough on its own) — remove them. Run after each ban-set revision; over-iterating tends to inflate the ban list.

## Interactions

| Stacks well with | Conflicts with | Order rule |
|---|---|---|
| `tokenizer-aware-lexicon.md` | — | `<do_not_confuse_with>` inside glossary terms is a local instance of subtraction — same pattern, narrower scope |
| `persona-clusters.md` | — | Subtractions inside `<lens_construction>` (e.g. `Do not default to mythology language`) harden the lens against centroid pull — see persona-clusters failure modes |
| `formatting-as-signal.md` | — | `<constraints>` and `<anti_patterns>` are the canonical block names for negative-space content; reuse them |
| `ordering-and-position.md` | — | Bans sit **after** the task they qualify, not before; this is a hard order rule |
| `references-and-evals.md` | — | The output contract / rubric should mirror the bans — if you ban X, the eval should flag X-violations |
| **Open-ended creative tasks** | ✗ | Bans constrain exploration; if the task is divergent, drop the technique |
| **Vague positive instructions** | ✗ | Bans cannot rescue an unclear ask; fix the positive first, then ban specific failure modes |
| **Hedge-laden prompter prose** | ✗ | Banning output hedges while using prompter hedges is contradictory; strip prompter hedges first |

**Order within a single prompt**: `<task>` → (bans inline or in `<anti_patterns>` block immediately after) → `<output_contract>` (with bans mirrored as eval criteria where applicable). Bans before the task float; bans after the output contract are too late to qualify generation.

## Failure modes

| Symptom | Diagnosis | Fix |
|---|---|---|
| Banned behaviour appears in output anyway | Ban was vague / wrong attractor named / placed before task and never bound to it | Make ban specific; pair with desired alternative; place after task block |
| Output is hedged despite explicit "do not hedge" instruction | Prompter's own prose is hedge-heavy; the model echoed the register | Strip hedges from prompter prose; the prompt's *own language* is the strongest signal about the intended register |
| Adding more bans stops helping or starts hurting | Ban count above ~7; signal collapse | Cap at 7; rewrite the positive instruction to absorb the bans |
| Output is bland, generic, refuses to take positions | Negative-only prompt — too many bans, not enough positive direction; model has nothing to assert | Restore positive instruction strength; bans should qualify, not replace, positive direction |
| Critical ban in ALL-CAPS ignored | Caps used everywhere in the prompt, no longer marks emphasis | Restrict caps to ≤2 critical bans; remove from all other instructions |
| Bans contradict user's stated goal | Anti-trigger missed: user wanted creative / exploratory / narrative output | Re-read the user request; drop bans that conflict with the actual ask |
| The ban list grows by one item every revision | Iterative band-aid for an unclear positive instruction | Stop. Rewrite the positive instruction. Then re-evaluate which bans are still needed |
| Output comments on what it's *not* doing ("I will not be vague, I will not...") | Bans are overweighted in the prompt; model is foregrounding suppression instead of producing the output | Reduce ban count; move surviving bans into `<constraints>` block to compartmentalise |
| Prompt with 0 bans gets centroid output; prompt with 8 bans gets centroid output | Bans are decorative or mis-targeted; the actual centroid attractor was never named | Run §1 again — articulate the trendslop output explicitly before banning |

## References

- [Transformer Feed-Forward Layers Are Key-Value Memories](https://arxiv.org/abs/2012.14913) — Geva et al., the K-V mechanism that explicit subtraction targets
- [Direct Preference Optimization](https://arxiv.org/abs/2305.18290) — Rafailov et al., why models trained with preference data respond to negative instructions
- [Constitutional AI](https://arxiv.org/abs/2212.08073) — Anthropic, principles-based steering including explicit prohibitions
- [Anthropic prompt engineering guide](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering) — practical patterns including constraint blocks
- See also: `mechanistic-foundations.md` (the why), `persona-clusters.md` (subtraction inside lens construction), `tokenizer-aware-lexicon.md` (`<do_not_confuse_with>` as local subtraction), `formatting-as-signal.md` (canonical block names for `<anti_patterns>` and `<constraints>`), `ordering-and-position.md` (bans after task, not before)
