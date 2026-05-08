# Formatting as Signal

## What

Treat the literal shape of the prompt — XML tags, headings, blank lines, indentation, list types, code fences, capitalisation, exact-string repetition — as **load-bearing signal that the tokenizer and attention mechanism actually consume**, not as cosmetic decoration for human readers.

## Mechanism

Three independent forces make formatting matter at the model level.

**Trained structural patterns.** Modern instruction-tuned models have seen millions of examples of certain structural conventions in their post-training data. Anthropic explicitly documents that Claude is trained to recognise XML tags as semantic boundaries; OpenAI models are trained on Markdown headings, fenced code blocks, and numbered lists in instruction-following datasets. Tags like `<task>`, `<context>`, `<output>`, `<thinking>`, `<constraints>` are not arbitrary strings — they are **patterns the model has learned to attend to as boundary tokens**. Using them is not aesthetic; it is invoking a trained convention.

**Tokenization is shape-sensitive.** The tokenizer does not see "a glossary section" — it sees a literal sequence of bytes. `<glossary>` and `glossary:` and `**Glossary**` and `# Glossary` tokenize to entirely different sequences and route through entirely different training distributions. A blank line tokenizes as one or two newline tokens that the model has learned to treat as a soft segment boundary. Indentation inside a code fence is tokenized consistently because the model has seen massive amounts of code; indentation outside code fences is ambiguous and may be stripped or fragmented.

**Position and attention sinks.** Block boundaries (tags, headings, blank lines) often act as **attention sinks** — positions the model attends to when it needs to "look up" what the current section is about. Well-named tags create local attention anchors that subsequent generation refers back to. Poorly-named or inconsistent tags create no such anchor and the model has to infer structure from prose alone.

These are correlates of trained behaviour, not literal computational guarantees. Different model families honour different conventions — Anthropic models lean heavily on XML, some open-source models ignore XML entirely and prefer Markdown. Validate per target (see `model-recon.md`).

## Trigger conditions

Apply deliberate formatting when **any** are true:

- The prompt has **multiple distinct semantic blocks** (role, task, context, examples, constraints, output contract). Each block needs its own boundary so the model can attend to them independently.
- The output must follow a **predictable structure** (JSON shape, sectioned report, code with explanations). The prompt's structure conditions the output's structure.
- The prompt **mixes content types**: prose + code + tables + lists. Without explicit boundaries, the model interpolates between modes and produces hybrids.
- The same string must appear in **multiple places** with the same meaning (an anchor, a variable name, a contract field). Exact repetition lets the model bind the same token sequence to the same role each time.
- The prompt will be **reused programmatically** with variable substitution. Tag-based templates survive substitution; prose-based templates degrade when content is injected.

Apply with **higher rigour** (every block tagged, headings consistent, no mixed conventions) when additionally:

- The receiving model is in the Claude family (XML strongly preferred per Anthropic docs).
- The prompt is part of a production agent or skill where the structure must survive across many invocations.

## Anti-trigger conditions

Do **not** over-format when **any** are true:

- **Single-question single-answer chat.** Wrapping `What time is it in Tokyo?` in five XML tags is dead weight that costs tokens and signals confusion about scope.
- **Casual or conversational tone.** Heavy structural scaffolding makes the model respond formally; if the user wants a chat, formatting fights the request.
- **Output is itself prose.** A creative-writing prompt asking for a short story does not benefit from the model having to navigate `<setting>`, `<character>`, `<mood>` blocks — flatten to a paragraph of intent.
- **Target model does not honour the convention.** Some smaller or older open-source models ignore XML tags entirely; using them is then noise. Recon first (`model-recon.md`).
- **Formatting competes with the user's content.** If the user is asking the model to write XML or Markdown, wrapping the prompt in the same syntax creates ambiguity about what is instruction and what is content. Use a different convention (e.g. fenced code blocks for the user-content sample).
- **Over-tagged.** Past ~7-10 distinct block types in a single prompt, the structural signal collapses into noise — the model has too many anchors to attend to and treats them as undifferentiated section markers.

If anti-triggers fire, fall back to **minimal formatting**: one or two blank-line-separated paragraphs with explicit role/intent in the first sentence.

## Procedure

### 1. Pick a primary structural convention and stick to it

Mixing conventions is worse than picking the wrong one. The model will treat XML tags and Markdown headings as parallel boundary signals, and when both appear it has to disambiguate which is the canonical structure. Pick one as primary, use the other only for content within blocks.

| Target model family | Primary convention | Secondary (within blocks) |
|---|---|---|
| Claude (Anthropic) | XML tags | Markdown for content (lists, code fences, bold) |
| GPT-4 / GPT-5 (OpenAI) | Markdown headings | XML acceptable but not preferred |
| Llama, Mistral, Gemma | Markdown headings + clear delimiters (`---`) | XML only if confirmed by recon |
| Smaller / older open-source | Plain prose with blank-line separators | Avoid heavy structure |

### 2. Use canonical block names

Tag/heading names that appear frequently in instruction-following training data are stronger anchors than improvised ones. Stick to the conventional set:

```
<role>           — who the model is (when using persona-clusters.md technique)
<task>           — the specific job to do
<context>        — background information
<input>          — the user-provided content to act on
<examples>       — few-shot demonstrations
<constraints>    — hard rules and prohibitions
<output_contract> or <output> — required shape of the response
<thinking>       — scratch reasoning area (Claude convention)
<glossary>       — local term definitions
<domain_anchors> — canonical jargon bundle
```

Anthropic docs at https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/use-xml-tags list the patterns Claude is trained on. Improvising new tag names (`<myTaskBlock>`) works but is weaker than reusing trained-on names.

### 3. Use blank lines as soft boundaries

Within a block, blank lines separate paragraphs and the model treats them as soft attention boundaries. Use them to separate sub-points that should not run together. Do not use blank lines as hard structural separators — that's what tags or headings are for.

```
<task>
Audit the code below for race conditions on shared mutable state.

Specifically: identify reads and writes to the global `cache` object that
are not protected by the lock at line 142.

Report each finding with file:line, severity, and a fix sketch.
</task>
```

The blank lines are reading aids that *also* register as soft boundaries. They cost almost nothing in tokens and materially improve the model's ability to treat the three sentences as distinct sub-instructions rather than one run-on directive.

### 4. Use code fences with explicit language tags

```python
def example():
    return 42
```

vs.

```
def example():
    return 42
```

The first routes through Python-specific training data because of the explicit `python` language tag; the second through generic code training data. For any code in the prompt — input to be analysed, examples, output format — use the language tag. Same applies to ` ```json `, ` ```sql `, ` ```yaml `, etc.

Indentation inside code fences is stable. Indentation outside code fences is ambiguous and should not be used as semantic signal.

### 5. Use lists deliberately by type

Different list shapes route through different training distributions:

- **Numbered lists** (`1. 2. 3.`) — common in step-by-step instruction-following data; use for **ordered procedures** the model should execute in sequence.
- **Bulleted lists** (`-` or `*`) — common in unordered enumeration; use for **independent items** with no implied order.
- **Tables** (Markdown `| col | col |` or HTML) — common in structured extraction; use when items have **multiple parallel attributes**.
- **Definition lists** (term: definition) — less common but reliable; use for **glossary content** when full XML overhead is excessive.

Mixing types within one section (a numbered list with bullets nested inside) works but the model may treat the nesting depth as semantic. Keep nesting shallow.

### 6. Repeat exact strings; do not paraphrase

If `idempotency` is a load-bearing anchor, every occurrence in the prompt should be the literal string `idempotency` — not `idempotent`, not `idempotence`, not `the property of idempotency`. The model binds the same token sequence to the same role across the prompt; paraphrasing breaks the binding and the model has to re-derive the connection.

```
weak (paraphrased):
  <task>Verify idempotency under retry.</task>
  <output_contract>Report any non-idempotent operations.</output_contract>

strong (exact):
  <task>Verify idempotency under retry.</task>
  <output_contract>Report any operations that violate idempotency.</output_contract>
```

This applies to anchor terms, variable names, contract field names, role labels — anything the prompt refers to in two or more places.

### 7. Use ALL-CAPS sparingly for hard imperatives

Words like `MUST`, `DO NOT`, `IMPORTANT`, `NEVER` in uppercase tokenize differently from their lowercase forms and appear in training data specifically as emphasis markers in instruction-following content. Used sparingly (≤3 per prompt), they elevate the marked instruction. Used everywhere, they degrade to noise — every imperative dilutes the others.

```
✓ One critical ban in caps:
  Do not modify the public API. Specifically, the function signatures of
  `process_payment` and `refund` MUST NOT change.

✗ Caps everywhere:
  YOU MUST AUDIT THE CODE. CHECK FOR RACE CONDITIONS. NEVER MODIFY THE
  PUBLIC API. ALWAYS REPORT FINDINGS WITH FILE AND LINE.
```

### 8. Place high-signal blocks at edges, low-signal in the middle

Position has its own technique file (`ordering-and-position.md`), but formatting interacts with it: tagged blocks at the **top** of the prompt (`<role>`, `<task>`, `<glossary>`) condition everything downstream; tagged blocks at the **bottom** (`<output_contract>`, `<constraints>`) gate generation. The middle is for context, examples, and input — material that supports the edges but doesn't drive the output shape.

## Validation

### Structural checks (the LLM can self-verify)

- [ ] Primary convention (XML or Markdown) chosen and used consistently.
- [ ] All opened tags are closed; no orphan or typo tags.
- [ ] No mixed conventions for the same kind of separator (e.g. some sections in `<task>` and others in `## Task`).
- [ ] Block names match the canonical set; improvised tag names are justified.
- [ ] Code fences specify language where applicable.
- [ ] Load-bearing strings appear with **exact** spelling in every occurrence.
- [ ] ALL-CAPS used at most 3× and only for hard imperatives.
- [ ] Block count ≤ ~7-10 distinct types (above this, structure collapses to noise).

### Probe-based validation

- **Order invariance** (`probes/position_pulse.py` adapted): permute non-edge blocks (move `<context>` and `<examples>` around). Output structure should survive permutation; output content should change only in ways consistent with order/recency rules from `ordering-and-position.md`. If the response shape collapses on permutation, the formatting is too brittle.
- **Strip-and-compare**: run the prompt with all formatting stripped to plain prose. If output is materially worse, the formatting was load-bearing — keep it. If output is comparable, the formatting was decorative — simplify.
- **Convention-conflict scan**: regex for both `<\w+>` tags and `^#{1,6}\s` Markdown headings; if both appear and represent the same kind of structural separator, flag for unification.

### Empirical sanity check

Run the prompt against three target models from different families (e.g. Claude, GPT-4, Llama). If output shape varies wildly, the formatting is over-specialised to one family — either commit to one family or simplify to a convention all three honour.

## Interactions

| Stacks well with | Conflicts with | Order rule |
|---|---|---|
| `persona-clusters.md` | — | Lens construction lives inside `<lens_construction>` and `<decision_tree>` tags; the tags ARE the load-bearing structure that makes the operationalization step register |
| `tokenizer-aware-lexicon.md` | — | `<glossary>` and `<domain_anchors>` are the canonical block names for lexicon content; reuse them, don't improvise |
| `ordering-and-position.md` | — | Tags carry positional weight as well as semantic — top-block tags condition more than bottom-block tags; this technique provides the *shapes*, that one provides the *placement* |
| `negative-space.md` | — | `<constraints>` and `<anti_patterns>` are the canonical homes for negative-space content |
| `references-and-evals.md` | — | `<sources>`, `<docs>`, `<evidence>` are canonical citation blocks |
| `model-recon.md` | — | Recon tells you which conventions the target honours — do recon **before** picking the primary structural convention |
| **Multiple primary conventions** | ✗ | XML and Markdown headings competing for the same role within one prompt — pick one, demote the other to within-block content |
| **Single-question chat** | ✗ | Wrapping `What's 2+2?` in `<task>...</task>` is over-engineering; respect the conversation scale |
| **User content using same syntax** | ✗ | If the user content is XML and the prompt is also XML, ambiguity about instruction-vs-content; switch the prompt to Markdown or wrap user content in a fenced code block |

**Order within a single prompt**: The natural top-to-bottom flow is `<role>` → `<glossary>` → `<domain_anchors>` → `<context>` → `<input>` → `<examples>` → `<task>` → `<constraints>` → `<output_contract>`. Not all blocks are required for every prompt. The two non-negotiables are: something near the top that establishes role/anchors, something near the bottom that gates the output shape.

## Failure modes

| Symptom | Diagnosis | Fix |
|---|---|---|
| Output ignores tagged sections; treats them as part of prose | Tag names are improvised or non-canonical, model didn't recognise structure | Switch to canonical names (`<task>`, `<context>`, `<output>`); confirm target-model convention via `model-recon.md` |
| Output uses tags from the prompt in its response when not asked to | Prompt over-formatted; model interpreted the structure as the requested output shape | Reduce structural overhead; or add explicit `<output_contract>` saying "respond in plain prose, do not echo prompt tags" |
| Output shape is unstable across runs | Mixed conventions OR too many block types (>10) OR non-canonical names | Unify on one primary convention; cap distinct block types; rename to canonical |
| Critical instruction ignored despite being in ALL-CAPS | Caps used everywhere, no longer marks emphasis | Remove caps from every other instruction; reserve for ≤3 truly critical bans |
| Code in the prompt parsed inconsistently | No language tag on code fence; or no fence at all | Add ` ```python ` (or appropriate language) to every code block |
| The same anchor produces different behaviour in two parts of the prompt | Anchor was paraphrased — `idempotent` in one place, `idempotency` in another | Repeat the **exact** string everywhere; pick canonical form once and stick to it |
| Output structure breaks when the prompt is reused via template substitution | Template variables sit inside prose without surrounding tag boundaries | Wrap every template variable in a tag (`<input>{{user_content}}</input>`) so substitution can't cross structural boundaries |
| Over-tagged prompt produces formal, robotic output to a casual question | Anti-trigger missed: heavy structure on conversational task | Strip to plain prose; reserve heavy formatting for genuinely structured tasks |
| XML-wrapped prompt fed to a model that doesn't honour XML | Convention mismatch with target model | Recon first; switch to Markdown or plain prose for non-Anthropic targets |

## References

- [Anthropic XML tags](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/use-xml-tags) — the trained convention for Claude
- [OpenAI prompt engineering guide](https://platform.openai.com/docs/guides/prompt-engineering) — Markdown-leaning convention
- [Attention Sinks in LLMs](https://arxiv.org/abs/2309.17453) — Xiao et al., why boundary tokens get disproportionate attention
- [Lost in the Middle](https://arxiv.org/abs/2307.03172) — Liu et al., positional sensitivity that interacts with structural placement
- [BPE for rare words](https://arxiv.org/abs/1508.07909) — why exact-string repetition matters
- See also: `mechanistic-foundations.md` (the why), `tokenizer-aware-lexicon.md` (what goes in `<glossary>` and `<domain_anchors>`), `persona-clusters.md` (what goes in `<lens_construction>` and `<decision_tree>`), `ordering-and-position.md` (where to place which tags), `negative-space.md` (what goes in `<constraints>` and `<anti_patterns>`), `model-recon.md` (which convention the target honours)
