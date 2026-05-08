# Mechanistic Foundations

This file defines the lower-level mechanics that prompt structure is trying to exploit.

## Mental Model

An LLM does not receive "meaning" directly. It receives tokens.

```
raw text
  -> tokenizer(text) = [t1, t2, t3, ... tn]
  -> embedding lookup E[t]
  -> positional signal P[i]
  -> hidden state X[i] = E[t_i] + P[i]
  -> transformer layers
  -> logits over next token
```

Prompting controls:

- Which tokens appear
- Which tokens co-occur
- Which tokens appear first, last, and near each other
- Which labels, examples, and schemas define the local distribution
- Which evidence and constraints are available in context

Prompting does not directly control:

- Model weights
- Training data coverage
- Hidden activations
- Attention heads
- Internal chain of thought

Good prompt design is therefore indirect control over a computation.

## Transformer Core

The useful simplified attention equation:

```
Q = X Wq
K = X Wk
V = X Wv

A = softmax((Q K^T) / sqrt(d))
Y = A V
```

Operational interpretation:

| Object | Prompt meaning |
|--------|----------------|
| `X` | Current token representations |
| `Q` | What each position is asking for |
| `K` | What each position offers as matchable signal |
| `V` | What information gets copied forward |
| `A` | Which positions influence which other positions |

Prompt engineering changes `X`. That changes every downstream matrix product.

## Encoding Is Distributional

Tokens that repeatedly occur in similar contexts during training tend to develop related internal representations.

```
"senior software engineer"
  -> broad cluster
  -> many inconsistent contexts
  -> average behavior

"Bill Gates"
  -> named-entity cluster
  -> speeches, interviews, books, Microsoft history, philanthropy, strategy
  -> tighter public-corpus attractor
```

This is a heuristic, not a literal database lookup. The model is not performing exact cosine search over a transparent corpus at inference time. But distributional geometry is a useful operational model: named entities, technical terms, canonical citations, and stable schemas often activate tighter regions than generic labels.

## Tokenizer Awareness

Tokenizers split text into subwords, bytes, or pieces. Different models use different tokenizers.

The same phrase can be:

```
"gross margin"       -> common compact tokens
"electroencephalography" -> multiple subword pieces
"CVE-2024-..."       -> punctuation-heavy fragments
"Q4FY26 ARR"         -> domain-specific fragments
```

Prompt implication:

- Use canonical industry terms.
- Define rare terms once in a glossary.
- Repeat exact labels when they are load-bearing.
- Avoid unnecessary synonym churn.
- Prefer stable identifiers for tests, files, functions, statutes, and APIs.

## Latent Anchors

An anchor is a token sequence that pulls generation toward a useful region.

Strong anchors:

- Named standards: `SOC 2 Type II`, `NIST SP 800-53`, `IFRS 15`
- Known frameworks: `Porter's Five Forces`, `CAPM`, `red-green-refactor`
- Library docs: `React Server Components`, `pytest fixtures`, `Stripe Checkout Sessions`
- Public figures with rich corpora: `Bill Gates`, `Warren Buffett`, `Mary Meeker`
- Exact tests: `pytest tests/test_billing.py::test_prorates_refund`

Weak anchors:

- "expert"
- "high quality"
- "robust"
- "senior"
- "world class"
- "best practices"

Weak anchors are not useless, but they are diffuse.

## Orthogonalization

Orthogonalization means separating concepts so they do not collapse into one blended instruction.

Bad:

```xml
<instructions>
Be rigorous, concise, creative, skeptical, practical, and investor-like.
</instructions>
```

The model receives one soup of adjectives.

Better:

```xml
<criteria_matrix>
Rows: lenses
Columns: questions

[Operator] x [Can this ship in 30 days?]
[Investor] x [Does this improve cash conversion?]
[Critic]   x [What assumption would kill the thesis?]
</criteria_matrix>
```

The prompt creates axes. Each axis receives a role in the computation.

## Matrix View of a Prompt

Instead of a paragraph, structure the prompt as a sparse matrix:

```
                feasibility   upside   downside   evidence
Bill Gates      ?             ?        ?          ?
Warren Buffett  ?             ?        ?          ?
Critic          ?             ?        ?          ?
```

XML version:

```xml
<analysis_matrix>
  <lens name="bill_gates">
    <criterion id="feasibility"/>
    <criterion id="technical_leverage"/>
    <criterion id="platform_effect"/>
  </lens>
  <lens name="warren_buffett">
    <criterion id="durable_moat"/>
    <criterion id="cash_generation"/>
    <criterion id="management_quality"/>
  </lens>
  <lens name="critic">
    <criterion id="failure_mode"/>
    <criterion id="disconfirming_evidence"/>
    <criterion id="hidden_incentive"/>
  </lens>
</analysis_matrix>
```

The model now has named axes instead of vague vibes.

## Training-Aware Prompting

Models are trained on mixtures of:

- Web text
- Code
- Books or licensed data
- Dialogue and instruction data
- Human preference data
- Synthetic data
- Tool-use traces
- Safety and refusal examples
- Domain-specific fine-tuning or RL

Prompt implication:

| Training source likely contains | Prompt should use |
|--------------------------------|-------------------|
| API docs and code examples | Exact library names, versions, function names |
| Public business writing | Named investor/operator lenses, filings, shareholder letters |
| Academic papers | Paper titles, arXiv IDs, definitions, equations |
| Stack Overflow / GitHub | Error messages, stack traces, tests, file paths |
| Instruction tuning | Clear delimiters, output contracts, explicit constraints |

## The Constraint Stack

Mechanistic prompt design uses layers:

```
domain anchors
  -> glossary
  -> evidence pack
  -> reasoning lens
  -> decision tree
  -> preregistered tests
  -> output contract
```

Each layer narrows the next-token distribution.

## Important Caveat

"Tokenizer-aware" does not mean hand-optimizing every token. It means designing prompts so the important semantic units are:

- Canonical
- Repeated consistently
- Separated by tags
- Positioned deliberately
- Supported by references
- Evaluated by tests

The payoff is highest on high-stakes, ambiguous, technical, or long-context tasks.

## References

- [Attention Is All You Need](https://arxiv.org/abs/1706.03762)
- [Neural Machine Translation of Rare Words with Subword Units](https://arxiv.org/abs/1508.07909)
- [SentencePiece](https://arxiv.org/abs/1808.06226)
- [OpenAI tiktoken](https://github.com/openai/tiktoken)
- [Hugging Face tokenizer summary](https://huggingface.co/docs/transformers/tokenizer_summary)
