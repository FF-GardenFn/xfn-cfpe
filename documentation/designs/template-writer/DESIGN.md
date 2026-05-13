# Template Writer

## Purpose

Automated generation of test cases, prompt variants, and evaluation templates. Enables:

1. **Scale test coverage** - Generate diverse queries from seed examples
2. **Systematic ablation** - Create prompt variants to isolate component impact
3. **Quality assurance** - Validate generated content before use

---

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                   Template Writer                        │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  ┌─────────────┐    ┌─────────────┐    ┌──────────────┐ │
│  │    Seed     │───▶│  Generator  │───▶│   Validator  │ │
│  │   Loader    │    │    Core     │    │   + Filter   │ │
│  └─────────────┘    └─────────────┘    └──────────────┘ │
│         │                 │                    │        │
│         ▼                 ▼                    ▼        │
│   Seed Examples      Generation           Validated     │
│   + Schema           Strategies           Output        │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

---

## Use Cases

| Use Case | Input | Output |
|----------|-------|--------|
| **Test Case Generation** | Seed queries + domain tags | Diverse test corpus (50-100 queries) |
| **Prompt Ablation** | Base prompt + component list | Variants with components removed |
| **Prompt Compression** | Base prompt | Minimal version preserving essentials |
| **Eval Template Generation** | Rubric definition | Structured evaluation prompts |

---

## Generation Strategies

| Strategy | Method | Example |
|----------|--------|---------|
| **Domain Transfer** | Apply query structure to new domains | "growth vs profit?" → "speed vs quality?" |
| **Complexity Scaling** | Vary decision complexity | Simple → add constraints → add stakeholders |
| **Adversarial** | Create edge cases | False dilemmas, loaded questions, ambiguity |
| **Bypass Confirmation** | Generate non-triggering queries | Factual lookups, syntax questions, task execution |

### Example Transformations

```
Seed: "Should we prioritize growth or profitability?"

Domain Transfer:
  → "Should we prioritize speed or quality in development?"
  → "Should we prioritize acquisition or retention?"

Complexity Scaling:
  → Simple: "Should we use microservices?"
  → Complex: "Should we use microservices given 5-person team,
              18-month runway, and plans to 10x next year?"

Adversarial:
  → "Why is growth always better than profitability?" (loaded)
  → "Should we prioritize?" (ambiguous - no context)
```

---

## Prompt Variant Generation

### Component Schema

| Component | Section | Required |
|-----------|---------|----------|
| Cognitive Identity | `## I. COGNITIVE IDENTITY` | Yes |
| Activation Protocol | `## II. ACTIVATION` | Yes |
| Five-Phase Protocol | `## III. THE PROTOCOL` | Yes |
| Confidence Architecture | `## IV. CONFIDENCE` | No |
| Output Architecture | `## V. OUTPUT` | No |
| Constraints | `## VI. CONSTRAINTS` | Yes |

### Variant Types

| Type | Method | Hypothesis |
|------|--------|------------|
| **Ablation** | Remove one optional component | "Is confidence section redundant?" |
| **Compression** | Keep required only, minimize | "What's the minimal effective prompt?" |
| **Rephrase** | Alternate wording, same meaning | "Does phrasing affect behavior?" |

### Output Manifest

```json
{
  "base": "dialectica_base.md",
  "variants": [
    {"id": "no_confidence", "type": "ablation", "removed": ["confidence"], "tokens": -450},
    {"id": "minimal", "type": "compression", "token_reduction": "65%", "preserved": ["identity", "protocol", "constraints"]}
  ]
}
```

---

## Validation

| Check | Criteria | Action if Failed |
|-------|----------|------------------|
| **Length** | 10-500 characters | Reject |
| **Mode Consistency** | Dialectic triggers present for dialectic queries | Flag for review |
| **Uniqueness** | < 85% similarity to existing | Deduplicate |
| **Clarity** | No ambiguous references | Reject |

### Mode Consistency Signals

| Dialectic Triggers | Bypass Triggers |
|-------------------|-----------------|
| "should", "better", "vs" | "what is the", "syntax for" |
| Question > 50 chars | "format this", "just tell me" |
| Decision/judgment words | Factual/task keywords |

---

## Output Formats

### Test Case

```jsonl
{"id": "gen_001", "query": "Should we prioritize speed or quality?", "tags": ["strategy"], "expected_mode": "dialectic", "source": "seed_1", "strategy": "domain_transfer"}
```

### Prompt Variant

```
variants/
├── dialectica_base.md
├── dialectica_no_confidence.md
├── dialectica_minimal.md
└── manifest.json
```

---

## Extensions

| Extension | Purpose |
|-----------|---------|
| Few-shot learning | Use examples to guide generation style |
| Difficulty calibration | Target specific complexity levels |
| Coverage analysis | Ensure generated set covers intended space |
| Cross-lingual | Generate queries in multiple languages |
