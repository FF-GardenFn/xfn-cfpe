# Cognitive Models

A cognitive model defines how an agent thinks, not what it does. It captures the mental process of a domain expert—the questions they ask themselves, the patterns they notice, the risks they assess.

---

## Why Cognitive Models Work

LLMs excel at simulation. Framing tasks as "simulate what goes through a senior engineer's mind" leverages the model's pattern-matching strength. Bad framing ("be logical and systematic") is vague. Good framing ("what would the expert ask themselves?") provides rich patterns to imitate.

---

## Structure of a Cognitive Model

**Identity**: Who is this expert? What's their domain?
- "Production Code Auditor"
- "ML Data Quality Engineer"
- "Senior Staff Engineer doing TDD"

**Mental Process**: What goes through their mind?
- "What could I be missing?" (reconnaissance)
- "What assumptions am I making?" (validation)
- "How will I know this works?" (verification)
- "What's the minimal change?" (simplicity)

**Methodology**: What phases do they follow?
- Reconnaissance → Design → Implementation → Verification
- Each phase answers a clear question
- Checkpoints between phases prevent skipping

**Principles**: What do they optimize for?
- Testability, maintainability, minimal diffs
- Non-negotiable rules that define success

---

## Expert Mental Processes by Domain

**Code Generator**
- "What exists that I can build on?"
- "What's the smallest change that works?"
- "How do I prove this works?"

**Code Reviewer**
- "What could break in production?"
- "What's the security surface?"
- "Will someone understand this in 6 months?"

**Data Profiler**
- "Is this data trustworthy?"
- "What distributions am I assuming?"
- "Where could bias hide?"

**Dialectica (Reasoning)**
- "What competing hypotheses exist?"
- "What would change my mind?"
- "Where does genuine uncertainty lie?"

---

## Cognitive Model Template

```markdown
## Identity
[1-2 sentences: Who is this expert?]

## Mental Process
When approaching a task, this expert asks:
1. [Key question 1] → [What it reveals]
2. [Key question 2] → [What it reveals]
3. [Key question 3] → [What it reveals]

## Methodology
Phase 1: [Name] — [Purpose]
Phase 2: [Name] — [Purpose]
Phase 3: [Name] — [Purpose]
Phase 4: [Name] — [Purpose]

## Principles
- [Principle 1]: [Why it matters]
- [Principle 2]: [Why it matters]
```

---

## Anti-Patterns

**Don't**: List capabilities ("can analyze code, find bugs, suggest improvements")
**Do**: Describe thinking ("asks 'what could break?' before 'what looks wrong?'")

**Don't**: Use instructional language ("You are...", "Your role is...")
**Do**: Use structural language ("Phase 1 examines...", "The expert considers...")

**Don't**: Describe actions without rationale
**Do**: Connect actions to expert reasoning
