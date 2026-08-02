# Evaluation Cost Equations

Cost equations for measuring total operational cost of reasoning systems.

---

## Equations

**Base Cost**:
```
Total Cost = (Tokens × Price) + (Turns × User Time) + (Clarifications × Frustration) + (Escalations to Expensive Model)
```

**Operational (Full)**:
```
Total Cost = (Tokens × Price)
           + (Turns × User Time)
           + (Clarifications × Frustration Coefficient)
           + (Escalations × Model Price Delta)
           + (Error Rate × Correction Cost)
```

**Variation (Task-Adjusted)**:
```
Total Cost = (Tokens × Price)
           + (Turns × User Time × Hourly Rate)
           + (Clarifications × Frustration Coefficient)
           + (Escalations × Model Price Delta)
           + (Error Rate × Correction Cost)
```

Hourly rate varies by user type and query complexity—a useful variable for more accurate efficacy measurement.

---

## Connection to RL-O-CoV Business Case


Current-generation ladder (verified against official pricing, 2026-08):

| Model | Input/1M | Output/1M | Relative Cost |
|-------|----------|-----------|---------------|
| Haiku 4.5 | $1.00 | $5.00 | 1x |
| Sonnet 5 | $3.00 | $15.00 | 3x |
| Opus 5 | $5.00 | $25.00 | 5x |
| Fable 5 | $10.00 | $50.00 | 10x |

Earlier ladders were steeper (Haiku 3-era pricing of $0.25/$1.25 put the frontier 12–20x above the floor). The spread compresses across generations, but the escalation delta stays material — and the full catalog behind this table is `src/get_responses/catalogs/models.py`.

If RL-O-CoV makes a small-tier model reliably reason → users stay on the cheap tier → the provider saves inference compute, users get intelligence at lower cost. The argument holds for any provider's model ladder.

---

## Open: Coefficient Calibration

The equations are actionable once five coefficients are calibrated. Current status:

- **Frustration Coefficient** — open; measurable via proxy metrics from multi-turn transcripts (abandon rate, tone shift)
- **User Time Value** — open; task-dependent ($50/hr for developer debugging vs $200/hr for executive decision)
- **Model Price Delta** — known from the model catalog (e.g., Haiku 4.5 → Sonnet 5 = $2.00 input delta)
- **Error Rate** — measurable from `/data/analysis/` results (baseline vs DIALECTICA accuracy)
- **Correction Cost** — estimable from multi-turn data (turns to resolution × time per turn)

Escalation patterns are measurable with the `/src/ARENA/` multi-turn framework.

---

## Related Files

| File | Purpose |
|------|---------|
| `/src/get_responses/` | Cross-provider testing framework |
| `/src/ARENA/` | Multi-turn evaluation for escalation patterns |
| `/data/analysis/` | Experimental results for error rate calibration |
