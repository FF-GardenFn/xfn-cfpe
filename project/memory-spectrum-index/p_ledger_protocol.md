# P-LEDGER / P-GATE — the recurring falsification protocol

**Status:** protocol v1.0 (2026-08-03). No rounds run. The first round opens with the next qualifying postmortem.
This file freezes the rules *before* any prediction so that neither the observables nor the scoring can drift
toward whatever makes the index look good.

## P-LEDGER

**Claim under test:** the cost split of an AI-assisted engineering project is predictable from repository
observables alone — before reading the project's own account of what it cost.

### Qualifying event

A newly published first-party postmortem of an agent-assisted project that discloses (at minimum) total spend or
token counts and a timeline. Third-party coverage does not qualify (secondary accounts embellish — cite the
primary or skip the round).

### Procedure, per round

1. **Freeze the target.** Record the postmortem's URL/title in a new file under [predictions/](./predictions/)
   **without reading past the headline.**
2. **Gather observables** (allowed list, closed): repository LOC and language mix; test coverage and assertion
   density (the E-proxy); issue-tracker history and dependency churn; public commit cadence. Nothing from the
   postmortem body, no secondary coverage of it.
3. **Commit the prediction:** the split `W : M_ext : M_tacit : D_fict` as percentages with ± bands, plus a
   feasibility call (any gates suspected). The git commit hash is the timestamp; the prediction is immutable
   after commit.
4. **Read the receipt. Score.** Per-column: inside band / outside band. Round verdict: hit if ≥3 of 4 columns
   inside bands *and* the feasibility call correct.
5. **Diagnose before refitting.** A miss produces a written diagnosis (which column, which observable misled,
   what the postmortem revealed that observables could not carry) *before* any parameter of the predictor
   changes. Diagnosis and refit are separate commits.

### Standing rules

- Rounds are never skipped because they look hard; skips are recorded with reasons.
- The running score (rounds, hits, per-column calibration) lives in [predictions/README.md](./predictions/README.md)
  and is updated every round, including misses.
- Survivorship caveat travels with every score: published postmortems are successes; the index's public track
  record is therefore its performance on the survivor distribution, stated as such.

## P-GATE

**Claim under test:** practitioners' self-models of their own tacit knowledge are informative but miscalibrated
in *both* directions — and the index can measure that.

Per instrumented task (requires a live run — lab or volunteer): pre-run tacit inventory ("what only you know;
what breaks without it; reconstructibility rating") → post-run comparison against realized gates/dual support →
confusion matrix (predicted-gating vs realized-gating). Success criterion for the *instrument*: nonzero
surprise rates in both cells off the diagonal. A diagonal-only matrix means the interview was theater; an
off-diagonal-only matrix means the plant is wrong.

## Round index

| Round | Target | Prediction commit | Verdict | Diagnosis |
|---|---|---|---|---|
| — | *(none yet — opens with the next qualifying postmortem)* | | | |
