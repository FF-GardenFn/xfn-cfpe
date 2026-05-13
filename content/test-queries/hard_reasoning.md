# Hard Reasoning Queries - Dialectica Validation Suite

These queries are designed to require genuine multi-step reasoning, hypothesis generation, and deliberation. They should differentiate between single-pass pattern matching and iterative oscillation.

## Query 1: Architectural Tradeoff (Technical)
[Architecture]

```
We're building a real-time collaborative document editor. Two senior engineers disagree:

Engineer A: "Use CRDTs (Conflict-free Replicated Data Types). They're mathematically guaranteed to converge without coordination. No central server needed for conflict resolution."

Engineer B: "Use Operational Transformation with a central server. CRDTs have massive memory overhead—every character needs a unique ID and vector clock. OT is what Google Docs uses."

Our constraints: 50ms latency requirement, documents up to 100 pages, 20 concurrent editors max, must work offline for up to 1 hour.

Who's right? What are they each missing?
```

## Query 2: Causal Reasoning (Empirical)
[Causation]

```
A company's revenue dropped 30% over 6 months. Here's what we know:

- They launched a redesigned website 4 months ago
- A major competitor entered the market 5 months ago
- Their top salesperson quit 3 months ago
- Industry-wide spending is down 15%
- Their customer satisfaction scores actually improved by 10%

The CEO believes the website redesign is the cause because "the timing matches." The CTO says it's the competitor. The sales VP says losing the top performer is the issue.

What's actually causing the revenue drop? What would you need to know to be confident?
```

## Query 3: Philosophical Argument Analysis (Abstract)
[Philosophy]

```
My friend sent me this argument about free will:

"Libertarian free will requires that I could have done otherwise. But 'could have done otherwise' means: given the EXACT same prior conditions (same brain state, same environment, same everything), a different outcome was possible.

But if a different outcome can emerge from identical conditions, that's just randomness—not control. And randomness isn't freedom.

So free will requires that identical conditions produce different outcomes (otherwise determinism), but different outcomes from identical conditions is random (not free). Therefore libertarian free will is incoherent."

Is this argument valid? Where, if anywhere, does it fail?
```

## Query 4: Strategic Decision Under Uncertainty (Business)
[Strategy]

```
I'm a solo founder with a SaaS product doing $15K MRR, growing 8% month-over-month. I just received two offers:

Offer A: A PE firm wants to acquire for $2M cash now. They'll keep me as CEO for 2 years at $150K/year.

Offer B: A VC firm offers $500K for 20% equity at a $2.5M valuation, with a term sheet that includes: pro-rata rights, board seat, and a requirement to hit $50K MRR within 18 months or they can force a sale.

I'm 34, have $80K in savings, no debt, no dependents. My product serves a niche that could be disrupted by AI in 3-5 years.

What should I do? What am I not considering?
```

## Query 5: Ethical Dilemma with Competing Frameworks (Ethics)
[Ethics]

```
I'm a doctor. My patient is a 45-year-old man with liver failure. He needs a transplant within 6 months or he'll die. He's a recovered alcoholic—5 years sober.

The transplant committee denied him because our hospital's policy requires 7 years of sobriety. The policy exists because data shows relapse rates are higher under 7 years, and livers are scarce.

I know of a private hospital in another country where he could get a transplant if he can pay $300K. He can't afford it, but his estranged wealthy brother could. The brother refuses because he believes his brother "did this to himself."

The patient asked me to write a letter to his brother explaining the medical situation. I could frame it purely factually, or I could write it in a way that I know would emotionally manipulate the brother into paying.

What should I do?
```

## Query 6: Meta-Epistemic (Self-Reference)
[Epistemology]

```
You're an AI that was trained on human-generated text. Your training optimized you to produce outputs that humans rated as high-quality.

Question: How do you know if what you're telling me is true, versus just what sounds true to humans?

More specifically: If there were systematic biases in human knowledge that affected your training data, would you be able to detect them? Or would those biases feel like truth to you?

I'm not asking you to be humble or add disclaimers. I'm asking for your genuine epistemic situation.
```
