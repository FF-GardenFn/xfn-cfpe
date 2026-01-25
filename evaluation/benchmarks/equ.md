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


| Model | Input/1M | Output/1M | Relative Cost |
|-------|----------|-----------|---------------|
| Haiku | $0.25 | $1.25 | 1x |
| Claude-4.5-Sonnet | $3.00 | $15.00 | ~12x |
| Opus | $5.00 | $25.00 | ~20x |

If RL-O-CoV makes Haiku reliably reason → users stay on Haiku → Anthropic saves compute, users get intelligence at lower cost.

---

## TODO: Coefficient Calibration

To make these equations actionable, need to calibrate:

- [ ] **Frustration Coefficient**: Measure via user studies or proxy metrics (abandon rate, tone shift)
- [ ] **User Time Value**: Task-dependent ($50/hr for developer debugging vs $200/hr for executive decision)
- [ ] **Model Price Delta**: Already known from catalog (Haiku→Sonnet = $2.75 input delta)
- [ ] **Error Rate**: Measure via `/data/analysis/` results (baseline vs DIALECTICA accuracy)
- [ ] **Correction Cost**: Estimate from multi-turn data (turns to resolution × time per turn)

 Use `/src/ANALYZER/` to collect user sentiment data that correlates with frustration or whatever tool anthropic has. 
 Use `/src/ARENA/` multi-turn framework to measure escalation patterns.

---

## Related Files

| File | Purpose |
|------|---------|
| `/src/get_responses/` | Cross-provider testing framework |
| `/src/ANALYZER/` | Sentiment data for frustration proxy |
| `/src/ARENA/` | Multi-turn evaluation for escalation patterns |
| `/data/analysis/` | Experimental results for error rate calibration |
