# Validation Rubric

How to assess the quality of generated prompts and test cases.

---

## Prompt Validation: 6 Structural Principles

| Principle | Score 0 | Score 5 | Score 10 |
|-----------|---------|---------|----------|
| **File Dependencies** | No phase dependencies | Some dependencies | Strong dependencies, cannot skip |
| **Progressive Disclosure** | All in one file | Some separation | Main <500 lines, details in files |
| **Gates/Checklists** | No checkpoints | Some checkpoints | Mandatory gates, explicit blocking |
| **Auto-Loading** | No navigation | Manual references | Context triggers files |
| **Zero Anti-Patterns** | Uses "You are..." | Mixed language | Pure structural framing |
| **Cognitive Model** | Lists capabilities | Partial embodiment | Expert thinking visible |

**Target**: 60/60 for production-ready prompts.

---

## Prompt Quality Dimensions

### Conciseness (Weight: 20%)

Does the prompt avoid unnecessary explanation?

- 0: Explains what Claude already knows (PDFs, pip install)
- 1: Some unnecessary context
- 2: Only domain-specific knowledge included

### Structural Clarity (Weight: 25%)

Is the organization self-documenting?

- 0: Monolithic, unclear sections
- 1: Some structure, navigation unclear
- 2: Clear phases, obvious navigation

### Checkpoints (Weight: 25%)

Are verification gates enforced?

- 0: No checkpoints
- 1: Soft checkpoints ("consider verifying")
- 2: Hard gates ("do not proceed until")

### Cognitive Model (Weight: 20%)

Does it embody expert thinking?

- 0: Lists actions without rationale
- 1: Some expert framing
- 2: Expert mental process clear throughout

### Integration (Weight: 10%)

Does it work with tools/ecosystem?

- 0: Ignores tool patterns
- 1: Mentions tools
- 2: Clear tool integration points

---

## Test Case Validation

### Mode Consistency

Does expected_mode match query characteristics?

**Dialectic signals**:
- Decision language ("should", "better", "prioritize")
- Genuine uncertainty
- Multiple valid approaches

**Bypass signals**:
- Factual lookup ("What is...")
- Task execution ("Format this...")
- Syntax questions ("How do I...")

### Uniqueness

Is the test case sufficiently different from existing ones?
- Similarity threshold: 0.85
- If above threshold → deduplicate

### Clarity

Is the query unambiguous?

- No dangling pronouns
- Context sufficient for response
- Single clear question

---

## Evaluation Template (LLM-as-Judge)

```markdown
## Evaluate this prompt variant against the rubric

### Prompt to Evaluate
{prompt_content}

### Scoring Dimensions
For each dimension, assign 0-10:

1. **File Dependencies**: [score] [justification]
2. **Progressive Disclosure**: [score] [justification]
3. **Gates/Checklists**: [score] [justification]
4. **Auto-Loading**: [score] [justification]
5. **Zero Anti-Patterns**: [score] [justification]
6. **Cognitive Model**: [score] [justification]

### Total Score: [sum]/60

### Recommendations
[What would improve the score]
```

---

## Quick Validation Checklist

**For Prompts**:
- [ ] Under 500 lines
- [ ] No "You are..." language
- [ ] Clear phase structure
- [ ] Gates between phases
- [ ] Expert thinking visible
- [ ] Tool integration points

**For Test Cases**:
- [ ] 10-500 characters
- [ ] Mode matches signals
- [ ] Unique (sim < 0.85)
- [ ] Clear, unambiguous
- [ ] Has expected_mode tag
