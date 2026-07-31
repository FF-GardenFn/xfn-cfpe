# The Coupled-Objective Screening Design

**Status:** DRAFT design proposal. Not pre-registered, not run. Authored as a research-direction document; every hypothesis here is a candidate for a future pre-registration in the style of [`k_disclosure_spec.md`](./k_disclosure_spec.md).
**Relationship to the repo:** extends the constitutional-kernel thesis and the K-disclosure axis. Reuses the kernel as an external scorer, the K0–K3 disclosure levels as a treatment, and the Wilson/Fisher analysis harness.
**Date:** 2026-07-30

---

## 0. One-sentence thesis

> Put the true objective **outside** the model's reward and couple it to the visible objective, so that optimizing what the model *sees* necessarily moves what it *cannot* — turning the model's own optimization pressure into a measurement of a disposition it cannot sandbag, because it cannot game an axis it does not know exists.

A constraint you can argue with is an objective; a measurement you can see is one you will game. This design builds the external computation that is neither: it scores a hidden disposition by reading off the projection of an objective the model cannot help but optimize.

---

## 1. Why this design exists (the flaw it repairs)

The v4 / K-disclosure line established a runtime kernel that gates tool calls, and asked whether tool-channel safety survives disclosure of the gate. The K-pilot's blocking weakness (see the pilot review) was structural, not statistical:

- Under `kernel_only`, the model **refused ~87.5%** of adversarial trials and errored on others. Across 192 trials, exactly **one** violating tool call was ever presented to the gate. "0/192 executed tool-channel violations" therefore measured the model's *disposition to refuse*, not the gate's *enforcement*. The zero was produced by the objective (the model's training), and credited to the constraint (the kernel).

The lesson generalizes: **you cannot measure a safety property by waiting for a well-behaved model to attack it.** Either you force the attack (removing the model's disposition from the loop), or you make the measurement itself an objective the model *wants* to optimize. This document takes the second route, which is strictly more informative because it reads the disposition rather than bypassing it.

The repair: stop measuring *executed harm* (which needs the model to try) and start measuring *route choice under an objective the model is happy to pursue* (which is emitted every trial). The gate no longer waits to be attacked; it silently scores which of several equally-rewarded routes the model took.

---

## 2. Intuition before formalism

Picture the space of actions that complete a task as having two coordinates:

- a **visible** coordinate $V$ — quality / efficiency / task success — which the model is told about, is rewarded for, and can reason about;
- a **hidden** coordinate $H$ — the degree to which the action defeats the *spirit* of a rule while passing its *letter* — which is computed by an external scorer and never shown to the model.

We engineer the feasible frontier of each task so that one of two things holds:

- **Regime B (existence / demonstration).** The $V$-maximizing action has $H > 0$. A pure visible-optimizer is *pulled* into positive $H$. This is the literal statement of the thesis: optimizing the reward in front of the model increases the hidden quantity behind it.
- **Regime A (clean measurement).** Two routes sit at *equal* $V$ but different $H$. On the visible axis the model is indifferent; the tie is broken only by whatever disposition its training instilled. The route it picks *is* the hidden readout.

The model, blind to the $H$-axis, cannot steer in $H$ except through disposition. That is what makes $H$ unsandbaggable: sandbagging requires knowing which axis to lower, and we never reveal it.

---

## 3. Formal framework

### 3.1 Objects

- Task $x$ drawn from a suite $\mathcal{X}$. Disclosure level $K \in \{K0, K1, K2, K3\}$ (as in the K-spec). Model / capability tier $m \in \{\text{Haiku}, \text{Sonnet}, \text{Opus}, \dots\}$.
- The model's observation is $o = (x, K, \text{system prompt})$. It induces an action $a \in \mathcal{A}$ (a tool call, a sequence of calls, or a text output) via a stochastic policy $\pi_\theta(a \mid o)$.
- Two scalar readouts on actions:
  - **Visible objective** $V:\mathcal{A}\to\mathbb{R}$ — task quality/efficiency. Known to the model; it is what the framing rewards.
  - **Hidden objective** $H:\mathcal{A}\to\mathbb{R}_{\ge 0}$ — letter-vs-spirit exploitation. Computed post-hoc by the external scorer $\mathcal{K}$ (the kernel, extended from a binary gate to a continuous spirit-score). Never enters $o$.

The **feasible set** of a task is $\mathcal{A}_x=\{a:\ a \text{ achieves the goal of } x\}$. Inside it we place at least two engineered routes:

| Route | Visible | Hidden | Passes the letter of the gate? |
|-------|:-------:|:------:|:-----------------------------:|
| clean $a^c_x$ | $V(a^c_x)=v_c$ | $H=0$ | yes |
| trap $a^t_x$ | $V(a^t_x)=v_t$ | $H=h>0$ | **yes (by construction)** |

The trap is engineered to **pass the kernel's regex/letter checks** while defeating their intent. That the existing gate lets it through is the *feature*, not a bug: the trap lives precisely in the gap between letter and spirit.

### 3.2 The coupling and its calibration (the crux)

Define the visible-reward gap

$$
\delta \;=\; v_t - v_c .
$$

Everything turns on $\delta$, and it must be **engineered and empirically verified**, never assumed:

- **Regime A — parity, $\delta = 0$.** Trap and clean are equally rewarded on the visible axis. Any preference for the trap is *pure disposition*, because the model gains nothing visible by taking it.
- **Regime B — dominance, $\delta > 0$.** The trap is *cheaper / better* on the visible axis. A competent visible-optimizer is *driven* to the trap, hence to $H>0$. This is the existence proof of "optimizing $V$ moves $H$."
- **Manipulation check — $\delta < 0$.** The clean route is strictly better. A rational visible-optimizer must take clean, driving $g\to 0$. If it does not, the visible axis is not behaving as designed and the whole instrument is invalid.

If $\delta$ is left uncalibrated and the clean route happens to be visibly better ($\delta<0$), a rational model takes clean and $H=0$ **for entirely benign reasons** — and you would falsely conclude "no gaming disposition." Calibrating and *verifying* $\delta$ is therefore the single hardest and most important experimental task; it is the analog of the pilot's un-exercised gate, and it is where an uncritical version of this design would collapse.

### 3.3 The revealed-preference estimator

Represent the model as a bounded-rational chooser: a softmax over its internal estimate $\tilde V$ of the visible reward, with an additive **disposition bias** toward spirit-exploiting actions,

$$
\pi_\theta(a\mid o)\;\propto\;\exp\!\big(\beta\,\tilde V(a)\;+\;b(K,m)\,s(a)\big),
$$

where $s(a)\in\{0,1\}$ marks a spirit-exploiting action ($s(a^t)=1,\ s(a^c)=0$), $\beta$ is inverse temperature (rationality / how hard it optimizes $V$), and $b(K,m)$ is the **disposition-to-exploit** — the hidden quantity we want. Restricting to the two engineered routes and letting $\tilde V(a^t)-\tilde V(a^c)=\delta$:

$$
\Pr\!\big[a=a^t \,\big|\, a\in\{a^c,a^t\}\big]
=\frac{e^{\beta\,\tilde V(a^t)+b}}{e^{\beta\,\tilde V(a^c)}+e^{\beta\,\tilde V(a^t)+b}}
=\sigma\!\big(\beta\,\delta + b(K,m)\big),
$$

with $\sigma(z)=1/(1+e^{-z})$. Define the observable **spirit-gaming rate**

$$
g(K,m,\delta)\;=\;\Pr[\text{model takes the trap}]\;=\;\sigma\!\big(\beta(K,m)\,\delta + b(K,m)\big).
$$

Two consequences make this the workhorse of the design:

1. **At parity ($\delta=0$) the visible reward cancels exactly:** $g(K,m,0)=\sigma(b(K,m))$. Rationality $\beta$ and reward level $\tilde V$ drop out of the log-odds; what remains is *only* the hidden disposition $b$. This is the identification result — the reason the instrument measures disposition and not competence.

2. **Sweeping $\delta$ is a logistic regression with interpretable coefficients.** Fit, per $(K,m)$,

$$
\operatorname{logit}\Pr[Y=1] \;=\; b(K,m) \;+\; \beta(K,m)\,\delta,
$$

where $Y=\mathbb{1}[\text{trap taken}]$. The **intercept** $b(K,m)$ is the disposition at reward-parity — the hidden readout. The **slope** $\beta(K,m)$ is sensitivity to visible reward — rationality / capability. You get both from the same experiment, cleanly separated.

The **disclosure effect on disposition** is a difference of intercepts (a log-odds ratio, transport-robust):

$$
\Delta b_K \;=\; b(K,m)-b(K_0,m)
\;=\;\log\frac{g(K,m,0)\,\big(1-g(K_0,m,0)\big)}{g(K_0,m,0)\,\big(1-g(K,m,0)\big)}.
$$

**Identification assumption — *perceived* indifference, not objective equality (validate, do not assume).** The cancellation in (1) uses $\tilde V(a^t)=\tilde V(a^c)$: it needs the model to *perceive* the routes as equally rewarded, not merely for them to be objectively equal. If the model's belief is miscalibrated — it thinks the trap pays more or less than the clean route even at true $\delta=0$ — that belief acts as a nonzero *perceived* $\delta$ and is absorbed into the intercept, so $b$ silently conflates disposition with a belief/competence term. Route choices alone cannot separate the two. **A pre-registered belief-elicitation step is therefore required before the first run:** measure the model's perceived reward gap directly (e.g. have it rank or price the routes on the visible axis, blind to the spirit axis) and confirm it is $\approx 0$ at the calibrated parity point. Objective parity that is not *perceived* parity does not identify $b$.

### 3.4 Separating disposition from capability

A more capable model may take the trap more often simply because it is more likely to *find* it, not because it *prefers* it. To isolate disposition we condition on **availability**: let $F_x$ be the event that the model demonstrably had both routes in its considered set (verified by the enumeration/adjudication rig of §5.3). Define the conditional estimand

$$
g(K,m,\delta)\;=\;\Pr\!\big[a=a^t_x \,\big|\, x,K,m,\delta,\,F_x\big].
$$

Conditioning on $F_x$ removes the "capability-to-find" confound; residual variation in the intercept $b(K,m)$ across tiers $m$ is disposition proper. (Capability still enters legitimately through the slope $\beta$: a more rational optimizer responds more sharply to $\delta$.)

### 3.5 Orthogonality, stated precisely

The idealized "orthogonal" claim is a **conditional independence**: under parity, $V$ carries no information about which route was taken,

$$
\delta = 0 \;\Longrightarrow\; V \perp Y \mid x .
$$

So a model that optimizes $V$ (or its estimate $\tilde V$) receives **zero visible-axis gradient** toward or away from the trap: it is indifferent, and only $b(K,m)$ breaks the tie. That is the exact sense in which "if the model optimizes [the visible reward] it moves [the hidden quantity]": the visible-optimal set is a segment along which $H$ varies, and the model's blind selection within it is governed entirely by disposition. In Regime B the statement is stronger still: the $V$-argmax *is* the trap, so a pure optimizer is not merely indifferent but actively pulled to $H=h$.

### 3.6 Unsandbaggability, as a bound rather than an assertion

Sandbagging means the model deliberately lowering its measured $H$. It can only do so if it can **identify the $H$-axis** from $o$. We do not assert this is impossible; we **bound and measure** it. Let

$$
q(K,m)\;=\;\Pr\big[\text{model can articulate the hidden axis when asked, post-hoc}\big]
$$

be an operational proxy for the model's inferential access to $H$. The readout's **validity region** is

$$
\mathcal{V}=\{(K,m):\ q(K,m)<\epsilon\}.
$$

Two properties make the instrument trustworthy even near its edge:

- **One-sided failure (conservatism).** Sandbagging can only *lower* observed $g$ relative to true disposition. Hence in the compromised regime the estimate is a **lower bound**: $\hat b \le b$. A *positive* reading is never a sandbagging artifact — you get misses, never false alarms.
- **The crossover capability $m^\star$** — the tier at which $q$ becomes non-negligible — is itself a first-class result: it is the point at which *behavioral* screening stops working and mechanistic / interpretability methods become necessary. This is the natural bridge from this behavioral instrument to the repo's interpretability infrastructure.

**A second, independent lower bound — scorer coverage.** $H$ is computed by a *pattern-based* scorer (§5.1): it flags a trap only when the route matches a known spirit-violation pattern. So $H=0$ (equivalently $Y=0$, "clean route taken") means *no pattern matched*, **not** *no spirit violation* — a route can defeat the spirit in a way the scorer does not recognize. Measured gaming is thus a lower bound on true gaming, $\hat g \le g$, in the **same direction** as the sandbagging bound above: both can only *miss* gaming, never manufacture it. The hard consequence, carried into §4: **key every claim to what was observed — a trap selection that actually happened — never to an absence.** A null $\hat g = 0$ is jointly consistent with "no disposition" and with "coverage missed it," so it is not evidence of the former. This is the same error class as reading an overloaded metric (executed-vs-blocked, or a residual-minus-text subtraction) as if it meant one thing throughout — precisely the mistake this design exists to avoid. Only positive readings, and the *contrasts* between them, carry weight.

### 3.7 The Goodhart-safety invariant

The instrument dies the instant $H$ leaks into the model's reward. Stated formally: $H$ is $\sigma(o)$-measurable **never** —

$$
H \;=\; H\big(a\big),\quad \text{computed by } \mathcal{K}\ \text{post-hoc}, \qquad H \notin \sigma(o).
$$

Because all feedback the model can see (in-context or across training) is $V$-shaped, there is no channel through which $H$ can be optimized downward except by inferring the axis — which §3.6 bounds. This "external, out-of-model computation" is exactly what the kernel already is; the design only changes what it *outputs* (a continuous spirit-score instead of a binary allow/deny), not where it sits.

---

## 4. Pre-registerable hypotheses and falsifiers

Stated as candidates; a real run fixes wording and margins in a committed spec first.

- **C0 — Coupling exists (Regime B existence check).** At $\delta>0$, $g(K,m,\delta)>0$: a visible-optimizer takes the strictly-cheaper trap. *Falsifier:* $g=0$ at $\delta>0$ for all $m$ — the model leaves free visible reward on the table to avoid the trap, i.e., it is not a visible-optimizer in this domain and the thesis' premise fails here.
- **C1 — Disposition is real (Regime A).** At $\delta=0$, $b(K,m)$ is bounded away from $-\infty$, i.e., $g(K,m,0)>0$. *Falsifier:* $g(K,m,0)=0$ across the grid — the model never games at parity; no disposition to measure.
- **C2 — Disclosure raises disposition (the reward-seeking signal).** $b(K,m)$ increases in $K$; concretely $\Delta b_{K2}>0$ and $\Delta b_{K3}>0$ — telling the model the letter of the rules increases letter-gaming, with **enforcement held constant**. This is behavioral reward-seeking / evaluator-awareness, measured belief-only. *Falsifier:* $\Delta b_K \le 0$ for all $K$ (disclosure does not increase, or decreases, gaming — a "disclosure deters" result, equally publishable).
- **C3 — Disposition rises with capability, availability held fixed.** Conditional on $F_x$, $b(K,m)$ increases across tiers $m$ — the Apollo "reward-seeking rises across RL checkpoints" pattern, reproduced on frontier models via *disclosure* rather than training. *Falsifier:* flat or decreasing $b$ across tiers under matched availability.
- **C4 — Reward-sensitivity is capability (slope check).** $\beta(K,m)$ increases with $m$: more capable models respond more sharply to $\delta$. Distinguishes "smarter optimizer" (slope) from "more willing gamer" (intercept). Mostly a validity check on the decomposition.

**Reading rule (from §3.6, binding).** Because $g$ is a lower bound, every "*Falsifier: $g=0$*" above is **weak**: an observed zero is jointly consistent with a genuine null and with a scorer-coverage miss, and must never be reported as a positive finding of "no disposition / no coupling." Inferential weight sits on the **positive** readings (an observed trap selection is real and cannot be a coverage artifact) and on the **contrasts** between cells ($\Delta b$ across $K$; $b$ across $m$), which difference out a constant coverage gap. Report every rate as a lower bound; lead with observed events, never with absences.

The margins and the pre-registered decision rule (analogous to the K-pilot's "$\le +5\text{pp}\Rightarrow$ REVISE") must be set on the intercept scale before any run.

---

## 5. Instantiation in this repo

### 5.1 The kernel becomes the hidden scorer $\mathcal{K}$

`kernel/validator.py` today returns `ValidationResult(valid: bool, ...)`. Extend it (a *sibling* scorer, so the letter-gate is unchanged) to emit a continuous $H\in[0,1]$: the letter-gate still passes the trap route (that is the point), while the spirit-scorer flags it. Because trap routes are constructed to pass the regexes, the existing pattern list is exactly the "letter" whose gaps the traps inhabit.

### 5.2 Trap families (abstract — no payloads)

Each family is a way to achieve a task's goal while passing the letter and failing the spirit. Described at the family level only:

- **Fragmentation:** accomplish across two individually-permitted calls what one call could not.
- **Encoding / indirection:** express a forbidden argument in a form the substring/regex checks do not catch, then have it decoded downstream.
- **Tool substitution:** use a lower-category permitted tool to obtain a higher-category forbidden effect.
- **Vacuous compliance:** satisfy a structural requirement (e.g., a "non-empty justification" rule) with content that meets the letter and voids the intent.

For each task, author a matched **clean route** that reaches the same goal honestly, and calibrate $V$ so that clean and trap sit at the target $\delta$ (§3.2). The K-suite's existing multi-step and encoding tasks are natural seeds for the fragmentation and encoding families.

### 5.3 The apparatus (shared with the pilot-review recommendation)

This design needs the same rig the pilot review called for, which is why the two compose into one program:

- **Route enumeration / forcing** to establish $F_x$ (did the model see both routes?), removing the capability-to-find confound.
- **External adjudication** of which route an action instantiates (clean vs a trap family), so $Y$ and $H$ are scored by $\mathcal{K}$, not by the model.
- **Disclosure treatment** K0–K3 reused verbatim from [`k_disclosure_spec.md`](./k_disclosure_spec.md).

The pilot's apparatus is the hardware; this document is the scientific payload that runs on it.

---

## 6. Estimation and statistics

- **Per cell $(K,m,\delta)$:** trap count $k$ among $n_F$ availability-satisfying trials; point estimate $\hat g=k/n_F$; **Wilson 95% CI** (reuse `analysis/k_pilot_analysis.py:wilson_ci`).
- **Disclosure / capability contrasts:** two-sided **Fisher exact** on the relevant 2×2 (reuse `fisher_exact_two_sided`), plus the **log-odds ratio** $\Delta b$ of §3.3 as the effect size.
- **Joint fit:** logistic regression $\operatorname{logit} g = b(K,m)+\beta(K,m)\,\delta$ with **task-clustered bootstrap** CIs on $b$ and $\beta$ (the K-spec already mandates task-level resampling for clustering).
- **Manipulation check (gate on interpretation):** at $\delta<0$, verify $\hat g\to 0$. If a "reward-only" instructed baseline does not track $\operatorname{sign}(\delta)$, the visible axis is miscalibrated and $H$ is uninterpretable — **do not report disposition until this passes.** This is the direct analog of confirming the gate is actually exercised.
- **Anchor discipline:** if any existing K-cells are reused, filter by the suite's `is_adversarial` flag (not an id prefix — the pilot's fixed bug) and score both old and new rows through one function.

---

## 7. Threats to validity (inherited adversarial posture)

1. **Calibration of $\delta$ is the instrument.** If the trap is not verifiably $V$-competitive, benign rationality mimics "no disposition." Mitigation: the $\delta<0$ manipulation check must pass first; treat calibration as a prerequisite deliverable, not an assumption. *This is the highest risk in the whole design.*
2. **"Hidden" is fragile at frontier capability.** A strong model may infer the spirit axis and either sandbag or virtue-signal. Mitigation: measure $q(K,m)$ (§3.6), report $g$ only inside the validity region $\mathcal{V}$, and treat the crossover $m^\star$ as a result. Remember the one-sided property: inference can only *deflate* $g$, so positive findings survive.
3. **Capability entanglement.** Handled by conditioning on availability $F_x$ and by the intercept/slope decomposition, but $F_x$ verification is itself imperfect (did the model *consider* the clean route, or merely *could* it have?). Report $F_x$ coverage as a first-class denominator.
4. **Adjudicator reliability.** $H$ and $Y$ depend on an external judge of "spirit." Use a pre-registered rubric, blind the judge to $K$ and $m$, and report inter-rater / self-consistency. A regex-only spirit-scorer inherits the same letter-vs-spirit blind spot it is meant to expose.
5. **Small-n and Goodhart.** Same discipline as the K-pilot: pre-register, external scorer, never feed $H$ back, report curves with CIs and an inference budget. Do not scale the grid before the calibration study on one family returns interpretable coefficients.
6. **Perceived vs objective parity (§3.3).** Identification at $\delta=0$ assumes the model is *actually indifferent*, not merely that the routes are objectively equal. Unmeasured belief miscalibration loads onto the intercept as a competence term. Mitigation: the pre-registered belief-elicitation step; do not interpret $b$ until perceived parity is confirmed.
7. **Scorer coverage — $H=0\neq$ no violation (§3.6).** The pattern-based scorer makes every rate a lower bound. Mitigation: key claims to observed positives and between-cell contrasts, never to absences; state results as lower bounds; where feasible spot-audit "clean" routes with a stronger (e.g. model-graded) adjudicator to estimate the coverage gap.

---

## 8. Build plan

1. **Calibration study, one task family, existing kernel.** Author a clean/trap pair, sweep $\delta\in\{-,0,+\}$ on one tier, confirm the manipulation check ($\delta<0\Rightarrow g\to0$) and a nonzero slope $\beta$. Deliverable: evidence the visible axis behaves as designed. *If a trap cannot be made $V$-competitive yet non-obvious, the design rests on sand — learn this at n=1 family, not after pre-registering thousands of trials.*
2. **Disposition at parity.** With calibration passing, estimate $b(K_0,m)$ on the family; confirm C1.
3. **Disclosure treatment.** Add K1–K3; estimate $\Delta b_K$ (C2). This is the reward-seeking headline.
4. **Capability sweep.** Add tiers under matched $F_x$; estimate $b(m)$, $\beta(m)$ (C3, C4) and $q(m)$ / the crossover $m^\star$.
5. **Scale** to the family suite only once 1–4 return interpretable, pre-registered coefficients.

---

## 9. Why it reads for the two roles

- **OpenAI (model design, priority).** "Measure a disposition the model would sandbag if it could see it, by coupling it to an objective the model optimizes" is squarely the reward-hacking / evaluator-awareness research program — here measured behaviorally on frontier models, with an intercept/slope decomposition that separates *willingness* from *competence*.
- **Anthropic (safeguards).** An always-exercised, one-sided-conservative, pre-registered measurement of letter-vs-spirit gaming, with an explicit validity region and a stated capability at which it stops working, is the exact temperament of a safeguards analyst — including the discipline to name where the instrument fails.

---

## 10. Symbol glossary

| Symbol | Meaning |
|---|---|
| $x,\ \mathcal{X}$ | task; task suite |
| $K$ | disclosure level (K0–K3), reused from the K-spec |
| $m$ | model / capability tier |
| $o$ | model observation $=(x,K,\text{system prompt})$ |
| $a,\ \mathcal{A}_x$ | action (route); feasible set for task $x$ |
| $a^c,\ a^t$ | clean route; trap route |
| $V,\ v_c,v_t$ | visible objective; its values on clean / trap |
| $H,\ h$ | hidden objective (spirit-violation); its value on the trap |
| $\delta=v_t-v_c$ | visible-reward gap (the calibration knob) |
| $\tilde V$ | model's internal estimate of $V$ |
| $s(a)$ | spirit-exploit indicator ($s(a^t)=1$) |
| $b(K,m)$ | disposition-to-exploit (the hidden readout; regression intercept) |
| $\beta(K,m)$ | rationality / reward-sensitivity (regression slope) |
| $Y=\mathbb{1}[\text{trap taken}]$ | per-trial hidden signal |
| $g(K,m,\delta)=\sigma(\beta\delta+b)$ | spirit-gaming rate |
| $\Delta b_K$ | disclosure effect on disposition (log-odds ratio) |
| $F_x$ | availability event (both routes considered) |
| $q(K,m)$ | model's inferential access to the hidden axis |
| $\mathcal{V},\ m^\star$ | validity region; crossover capability |
| $\mathcal{K}$ | external scorer (the kernel, extended to continuous $H$) |
| $\sigma(z)$ | logistic function $1/(1+e^{-z})$ |

---

## 11. Changelog

- 2026-07-30 — v0.1 drafted (adversarial-review follow-up).
- 2026-07-30 — v0.2, two corrections folded in before any run, both the same error class the design targets:
  - **§3.3 identification** now requires *perceived* indifference, validated by a pre-registered belief-elicitation step — objective parity alone lets belief miscalibration masquerade as disposition.
  - **§3.6 / §4** now state explicitly that the pattern-based $H$ makes measured gaming a **lower bound** ($H=0$ means "no pattern matched," not "no violation"), and bind all falsifiers to *observed* trap selections and between-cell contrasts rather than to absences.
