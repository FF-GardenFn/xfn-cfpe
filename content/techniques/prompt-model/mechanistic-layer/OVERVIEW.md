# Mechanistic Prompt Layer — Router

This file is the **entry point** for the mechanistic layer. It is consulted
first by the skill (and by humans) before any technique is applied. Its job
is dispatch, not exposition.

For the conceptual "why" — what these techniques are reaching at — see
`mechanistic-foundations.md`. This file does not repeat it.

For the flatter machine-readable dispatch table, see `preconditions-catalog.md`.
This file is for human reading; that one is for agent dispatch.

## How to use this file

You arrive here with one of three kinds of artefact:

- A **request**: a user has asked for a prompt, edit, or analysis.
- A **draft**: a prompt-in-progress that needs evaluation.
- A **target model + task**: design from scratch.

For each of those, the dispatch is:

1. Run **`model-recon.md` first** — it gates everything downstream.
2. Walk the **trigger-condition matrix** below. Every row whose conditions
   fire pulls in the corresponding technique file.
3. Apply each consulted file's `## Procedure` in dispatch order.
4. Run **`validation-and-integration.md` last** — it integrates the per-file
   outputs into the composite go / no-go decision.

## Technique catalog

| File | Role in the dispatch | When it runs |
|---|---|---|
| `model-recon.md` | Gate. Identifies tokenizer, context window, channel hierarchy, training cutoff. Constrains every downstream choice. | First. Always, when target is named. |
| `tokenizer-aware-lexicon.md` | Builds canonical anchor bundle and glossary. Locks load-bearing terms. | Whenever the task is technical / domain-rich. |
| `persona-clusters.md` | Constructs named or invented lenses, operationalises into decision trees. | When task is judgment / evaluation / design / critique. |
| `ordering-and-position.md` | Head/middle/tail placement, head-tail duplication, option-order neutralisation. | Whenever multi-block, >4K tokens, or ranking/comparison. |
| `formatting-as-signal.md` | XML vs Markdown convention, canonical block names, exact-string repetition. | Whenever the prompt has multiple semantic blocks. |
| `negative-space.md` | Explicit subtraction of named centroid attractors; hedge stripping. | When known-bad output centroid is predictable. |
| `references-and-evals.md` | Track A source pack + Track B preregistered tests / falsifiers. | When facts must be defensible OR success criteria are namable. |
| `validation-and-integration.md` | Post-flight composite gate. Production go / no-go. | Last. Always before deployment. |

The substrate file `mechanistic-foundations.md` is the conceptual "why" —
not part of the dispatch loop, consulted when a downstream technique's
mechanism is unclear.

## Trigger-condition matrix

If a signal in the **left** column matches the request / draft / target,
consult the file in the **right** column. Multiple rows can fire; consult
all that match. Rows are not mutually exclusive.

### Target model and tokenization

| Signal | Consult |
|---|---|
| Target model is named (production, API, agent) | `model-recon.md` (first, always) |
| Context window > 32K tokens | `ordering-and-position.md` (head-tail dup, context index) |
| Training cutoff predates required facts | `references-and-evals.md` Track A (mandatory) |
| Tool access available | `references-and-evals.md` §B.2 (executable tests) |
| Channel hierarchy strict (system / user / tool gradient) | `ordering-and-position.md` §8 |
| Vision-capable target | `references-and-evals.md` §A.5 (screenshots first-class) |
| Reasoning model (o1, o3, Claude extended thinking) | `model-recon.md` §5 + `persona-clusters.md` (less CoT scaffolding) |

### Domain and lexicon

| Signal | Consult |
|---|---|
| Technical domain with named standards (RFC, ISO, NIST, CWE, SLO) | `tokenizer-aware-lexicon.md` |
| Vague verbs (`analyze`, `review`, `look at`) attached to domain-specific objects | `tokenizer-aware-lexicon.md` |
| Cross-domain synthesis with polysemy risk | `tokenizer-aware-lexicon.md` (high density + disambiguation) |
| Library / API explicitly referenced | `tokenizer-aware-lexicon.md` §6 (library anchors) |

### Judgment and lens

| Signal | Consult |
|---|---|
| Task is judgment / evaluation / design / critique | `persona-clusters.md` |
| Trade-offs across orthogonal axes (correctness vs performance, formal vs operational) | `persona-clusters.md` (stacked lens) |
| User wants stress-tested recommendation | `persona-clusters.md` (persona loop with convergence rule) |
| Internal-workflow domain with no public figure fits | `persona-clusters.md` (invented persona path) |

### Position and structure

| Signal | Consult |
|---|---|
| Multi-block prompt (role + task + context + examples + constraints) | `ordering-and-position.md` + `formatting-as-signal.md` |
| Context > 4K tokens | `ordering-and-position.md` |
| Ranking / selection / comparison of multiple candidates | `ordering-and-position.md` (option-order neutralisation) |
| Multi-channel input (system / developer / user / tool / retrieved) | `ordering-and-position.md` §8 |

### Formatting

| Signal | Consult |
|---|---|
| Output must follow predictable structure (JSON, sectioned report, code+explanation) | `formatting-as-signal.md` |
| Prompt mixes content types (prose + code + tables + lists) | `formatting-as-signal.md` |
| Prompt reused programmatically with variable substitution | `formatting-as-signal.md` (exact-string repetition) |

### Negative space

| Signal | Consult |
|---|---|
| Known-bad output centroid is predictable (consultancy speak, generic security advice) | `negative-space.md` |
| Revision after observed centroid-trap output | `negative-space.md` |
| Domain has well-known anti-patterns with names (SOLID, OWASP, data leakage) | `negative-space.md` |
| Output evaluated against rubric with named disqualifying failure modes | `negative-space.md` (mirror rubric as bans) |

### References and evals

| Signal | Consult |
|---|---|
| Task involves factual claims that can be wrong | `references-and-evals.md` Track A |
| High-stakes; fluent-but-wrong materially worse than honest "don't know" | `references-and-evals.md` Track A |
| Code generation | `references-and-evals.md` Track B (preregistered tests) |
| Strategic / analytical task | `references-and-evals.md` Track B (falsifiability) |
| LLM-as-judge will score the output | `references-and-evals.md` §B.4 |

### Validation gate

| Signal | Consult |
|---|---|
| Prompt moving from draft to production deployment | `validation-and-integration.md` |
| Part of versioned skill / plugin where regressions matter | `validation-and-integration.md` |
| Regulated workflow (medical / legal / financial / safety-critical) | `validation-and-integration.md` (full inter-rater) |
| Author is the only reviewer | `validation-and-integration.md` §3 (LLM judge primary, author secondary) |

## Anti-trigger short-list

If **all** apply, short-circuit the dispatch and write the prompt with plain
prose:

- Single-question single-answer chat
- Pure execution task (translate, sort, format-convert) with no judgment surface
- Prompt < 500 tokens
- Throwaway / one-off, not deployed to production
- Target model is small / specialised / weak instruction tuning

Technique overhead exceeds prompt lifetime value in these cases.

## Operating principle

Every prompt component must justify its position in the token stream.

```
HIGH SIGNAL FIRST: task, success criteria, domain anchors, lens construction
MIDDLE: evidence, examples, candidate options, context
HIGH SIGNAL LAST: output contract, constraints, tests, final decision rule
```

The goal is not to "trick" the model. The goal is to reduce ambiguity in the
computation the prompt induces.

## Minimal dispatch example

Request: *"Audit this Stripe-Checkout integration for race conditions on
webhook idempotency."*

Dispatch:

1. `model-recon.md` (target = Claude Sonnet, ~200K window, tool access available).
2. `tokenizer-aware-lexicon.md` — domain is application_security; canonical bundle: `idempotency`, `race condition`, `webhook replay`, `event deduplication`, `at-least-once delivery`.
3. `persona-clusters.md` — invented persona (Stripe-style payment-systems engineer); decision tree: deduplication keys, idempotency tokens, ordering guarantees, partial-failure recovery.
4. `ordering-and-position.md` — task near tail (judgment); option-order n/a; related rules and code adjacent.
5. `formatting-as-signal.md` — XML primary (Claude); `<task>`, `<input>`, `<anti_patterns>`, `<output_contract>` blocks.
6. `negative-space.md` — explicit bans on style commentary, naming changes, library-recommendation drift.
7. `references-and-evals.md` — Track A: Stripe official idempotency docs as authoritative source; Track B: preregistered test commands for the affected webhooks.
8. `validation-and-integration.md` — score against composite gate before shipping.

Eight files consulted; all eight relevant; nothing decorative. This is the
shape of a clean dispatch.

## Reference basis

This layer builds on:

- Transformer attention: [Attention Is All You Need](https://arxiv.org/abs/1706.03762)
- Subword tokenization: [BPE for rare words](https://arxiv.org/abs/1508.07909), [SentencePiece](https://arxiv.org/abs/1808.06226)
- Long-context placement effects: [Lost in the Middle](https://arxiv.org/abs/2307.03172)
- Prompt order instability: [Calibrate Before Use](https://proceedings.mlr.press/v139/zhao21c.html)
- In-context learning mechanics: [Rethinking Demonstrations](https://arxiv.org/abs/2202.12837)
- Chain-of-thought scaffolding: [Chain-of-Thought Prompting](https://arxiv.org/abs/2201.11903), [Self-Consistency](https://arxiv.org/abs/2203.11171)
- Channel hierarchy: [The Instruction Hierarchy](https://arxiv.org/abs/2404.13208)
- Tokenizer tools: [OpenAI tiktoken](https://github.com/openai/tiktoken), [Hugging Face tokenizers](https://huggingface.co/docs/transformers/tokenizer_summary)
- XML prompt structure: [Anthropic XML tags](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/use-xml-tags)
