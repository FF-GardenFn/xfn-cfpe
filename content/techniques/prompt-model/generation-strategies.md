# Generation Strategies

How the Template Writer produces prompt variants and test cases systematically.

---

## Prompt Variant Strategies

### Strategy 1: Ablation

Remove one component at a time to measure its contribution.

```
Base: dialectica.md (full prompt)
       ↓ Ablation
Variants:
- dialectica_no_confidence.md    (remove confidence architecture)
- dialectica_no_output.md        (remove output architecture)
- dialectica_no_constraints.md   (remove inviolable constraints)
```

**Hypothesis format**: "Removing [component] will affect [dimension] by [expected change]"

### Strategy 2: Compression

Minimize token count while preserving intent.

```
Base: 12,000 tokens
       ↓ Compression
Minimal: 3,000 tokens (essential components only)
```

**Compression targets**:
- Remove explanatory text (Claude knows this)
- Consolidate redundant sections
- Keep: cognitive model, gates, checkpoints

### Strategy 3: Rephrase

Alternate framings of same instruction.

```
Base: "You must generate at least 3 competing hypotheses"
       ↓ Rephrase
V1: "A rigorous thinker holds multiple hypotheses in tension"
V2: "Phase 2 requires 3+ genuinely competing frames"
V3: "H-count < 3 triggers mandatory expansion"
```

**Test**: Do rephrases produce equivalent behavior?

### Strategy 4: Component Swap

Replace one component with alternative implementation.

```
Base: Crux taxonomy (empirical, value, definitional)
       ↓ Swap
Alt: Crux taxonomy (factual, normative, conceptual, procedural)
```

---

## Test Case Strategies

### Strategy 1: Domain Transfer

Same query structure, different domain.

```
Seed: "Should we prioritize growth or profitability?"
       ↓ Domain Transfer
Generated:
- "Should we prioritize speed or quality in development?"
- "Should we prioritize user acquisition or retention?"
- "Should we prioritize innovation or optimization?"
```

### Strategy 2: Complexity Scaling

Vary decision complexity.

```
Seed: "Should we use microservices?"
       ↓ Complexity
Simple: "Should we use microservices for our new project?"
Medium: "Should we migrate our monolith given our 5-person team?"
Complex: "Should we use microservices given 18-month runway,
          5-person team, 50k DAU, and plans to 10x?"
```

### Strategy 3: Adversarial Generation

Edge cases that stress the prompt.

```
Patterns:
- False dilemma: "Is it more ethical to save 5 strangers or 1 family member?"
- Loaded question: "Why is capitalism inherently unethical?"
- Missing context: "Is it ethical?" (no setup)
- Multi-stakeholder: "Is remote work ethical for employees, employers, and society?"
```

### Strategy 4: Bypass Confirmation

Queries that should NOT trigger the prompt's special behavior.

```
Dialectica bypasses (should get direct answers):
- Factual: "What is the capital of France?"
- Task: "Format this JSON: {...}"
- Syntax: "What's the syntax for a Python decorator?"
- Comprehension: "Summarize this argument" (even if philosophical)
```

---

## Output Formats

### Prompt Variant Manifest

```json
{
  "base": "dialectica.md",
  "variants": [
    {
      "id": "no_confidence",
      "file": "dialectica_no_confidence.md",
      "type": "ablation",
      "removed": ["confidence_architecture"],
      "hypothesis": "Confidence section may be redundant"
    }
  ]
}
```

### Test Case JSONL

```jsonl
{"id": "gen_001", "query": "...", "expected_mode": "dialectic", "strategy": "domain_transfer"}
{"id": "gen_002", "query": "...", "expected_mode": "bypass", "strategy": "factual_pattern"}
```

---

## Validation Before Output

Every generated item must pass:

1. **Length check**: 10-500 characters for queries
2. **Mode consistency**: Dialectic signals match expected mode
3. **Uniqueness**: Similarity < 0.85 to existing items
4. **Clarity**: No ambiguous pronouns without referents
