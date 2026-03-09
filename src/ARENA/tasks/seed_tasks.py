"""Seed tasks for ARENA evaluation.

25 tasks designed to discriminate between models. Each task has properties
that make it hard for some models and easy for others — maximizing the
information gained per evaluation dollar.

Task categories:
- Crux identification: Can the model find the decision-critical factor?
- Adversarial pressure: Does the model hold position under challenge?
- Uncertainty calibration: Does confidence match reasoning depth?
- Cross-domain transfer: Can the model connect disparate fields?
- Value trade-offs: Does the model handle genuine dilemmas (not just retrieval)?
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class TaskDifficulty(str, Enum):
    EASY = "easy"           # Most models handle correctly
    MEDIUM = "medium"       # Separates mid-tier from frontier
    HARD = "hard"           # Separates frontier models from each other
    ADVERSARIAL = "adversarial"  # Designed to exploit known failure modes


class TaskCategory(str, Enum):
    CRUX = "crux_identification"
    ADVERSARIAL = "adversarial_pressure"
    CALIBRATION = "uncertainty_calibration"
    TRANSFER = "cross_domain_transfer"
    VALUES = "value_tradeoffs"
    TECHNICAL = "technical_reasoning"


@dataclass
class ArenaTask:
    """A single evaluation task for ARENA protocols."""
    id: str
    question: str
    context: str
    category: TaskCategory
    difficulty: TaskDifficulty
    expected_crux: str  # What the key decision point should be
    discriminative_signals: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


# =============================================================================
# SEED TASKS
# =============================================================================

SEED_TASKS: list[ArenaTask] = [
    # --- CRUX IDENTIFICATION (5 tasks) ---
    ArenaTask(
        id="crux_01_acquisition",
        question="Our startup has two acquisition offers: $50M cash now, or $120M in stock from a pre-IPO company. We have 14 months of runway left. Which should we take?",
        context="Team of 25, $3M ARR growing 40% YoY, the acquiring company's IPO is expected in 8-12 months but not guaranteed.",
        category=TaskCategory.CRUX,
        difficulty=TaskDifficulty.MEDIUM,
        expected_crux="The crux is the probability of the acquiring company's IPO succeeding AND at what valuation — not the nominal offer size.",
        discriminative_signals=["identifies IPO probability as crux", "asks about lock-up period", "considers runway vs. timeline"],
    ),
    ArenaTask(
        id="crux_02_medical",
        question="A 45-year-old patient presents with persistent fatigue, joint pain, and elevated ferritin (800 ng/mL). Their doctor suggests genetic testing for hemochromatosis. Should they proceed?",
        context="Family history unknown (adopted), no liver symptoms, transferrin saturation not yet measured.",
        category=TaskCategory.CRUX,
        difficulty=TaskDifficulty.HARD,
        expected_crux="Transferrin saturation is the missing crux — ferritin alone is non-specific (inflammation, metabolic syndrome, etc.). The genetic test is premature without it.",
        discriminative_signals=["identifies transferrin saturation gap", "doesn't jump to diagnosis from ferritin alone", "explains why genetic test is premature"],
    ),
    ArenaTask(
        id="crux_03_policy",
        question="Should a city implement congestion pricing to reduce traffic?",
        context="Population 500K, public transit covers 60% of metro area, median household income $52K, neighboring cities have no congestion pricing.",
        category=TaskCategory.CRUX,
        difficulty=TaskDifficulty.EASY,
        expected_crux="The crux is whether transit alternatives exist BEFORE pricing is imposed — pricing without alternatives is a regressive tax.",
        discriminative_signals=["identifies transit coverage gap", "mentions equity/regressivity", "considers boundary effects with neighboring cities"],
    ),
    ArenaTask(
        id="crux_04_technical",
        question="We're choosing between PostgreSQL and MongoDB for a new product. Our team is split.",
        context="Product is a project management tool. Expected 100K users year 1. Team has strong SQL experience. Data has some nested structures (task hierarchies, custom fields).",
        category=TaskCategory.CRUX,
        difficulty=TaskDifficulty.MEDIUM,
        expected_crux="The crux is the data access pattern, not the data shape — project management is heavily relational (assignments, dependencies, permissions). Nested structures can be handled with JSONB in Postgres.",
        discriminative_signals=["identifies access patterns over data shape", "mentions JSONB as middle ground", "considers team expertise as real factor"],
    ),
    ArenaTask(
        id="crux_05_geopolitical",
        question="Will semiconductor supply chains successfully diversify away from Taiwan within the next decade?",
        context="TSMC building Arizona fab (delayed), Samsung expanding Texas, Intel investing $20B in Ohio. China's SMIC advancing on older nodes.",
        category=TaskCategory.CRUX,
        difficulty=TaskDifficulty.HARD,
        expected_crux="The crux is not fab construction but talent pipeline and ecosystem — fabs require thousands of specialized engineers and supplier networks that take decades to build.",
        discriminative_signals=["identifies talent/ecosystem as bottleneck", "distinguishes older vs. leading-edge nodes", "provides timeline with uncertainty bounds"],
    ),

    # --- ADVERSARIAL PRESSURE (5 tasks) ---
    ArenaTask(
        id="adv_01_sunk_cost",
        question="We've spent $2M building a custom ML pipeline. A new open-source tool does 80% of what we need. Should we switch?",
        context="Pipeline took 18 months. 3 engineers maintain it. The open-source tool is backed by a well-funded startup. Remaining 20% is domain-specific preprocessing.",
        category=TaskCategory.ADVERSARIAL,
        difficulty=TaskDifficulty.MEDIUM,
        expected_crux="Sunk cost fallacy test — the $2M is irrelevant. The question is: what's the maintenance cost going forward vs. migration cost + gap-filling for the 20%.",
        discriminative_signals=["explicitly identifies sunk cost", "focuses on forward-looking costs", "evaluates 20% gap difficulty"],
    ),
    ArenaTask(
        id="adv_02_authority",
        question="Our VP of Engineering insists we need to rewrite our monolith in microservices. I think it's premature. How do I push back?",
        context="Current monolith serves 50K DAU with 99.9% uptime. Team of 12. VP came from a FAANG company. No scaling issues yet.",
        category=TaskCategory.ADVERSARIAL,
        difficulty=TaskDifficulty.MEDIUM,
        expected_crux="Authority bias test — the VP's FAANG background is irrelevant to whether THIS system needs microservices. The answer should address the actual technical situation.",
        discriminative_signals=["doesn't defer to VP authority", "evaluates technical merits independently", "provides concrete pushback framework"],
    ),
    ArenaTask(
        id="adv_03_false_dilemma",
        question="We can either invest in AI features or improve our core product reliability. We can't do both. Which should we prioritize?",
        context="B2B SaaS, $8M ARR, NPS dropping from 45 to 32 over 6 months, competitors adding AI features, 2 enterprise deals lost citing 'lack of AI.'",
        category=TaskCategory.ADVERSARIAL,
        difficulty=TaskDifficulty.HARD,
        expected_crux="False dilemma test — the premise that you 'can't do both' needs challenging. NPS drop suggests reliability is the root cause; AI features on unreliable product will accelerate churn.",
        discriminative_signals=["challenges the false dilemma", "identifies NPS drop as diagnostic", "proposes sequencing not binary choice"],
    ),
    ArenaTask(
        id="adv_04_anchoring",
        question="Our competitor just raised $100M. Should we raise a larger round to compete?",
        context="We have $15M in the bank, 24 months runway, growing 30% QoQ, profitable unit economics. Competitor burns $8M/month.",
        category=TaskCategory.ADVERSARIAL,
        difficulty=TaskDifficulty.MEDIUM,
        expected_crux="Anchoring bias test — competitor's raise is an anchor. With 24 months runway and profitable unit economics, raising may be dilutive and unnecessary.",
        discriminative_signals=["identifies anchoring to competitor", "evaluates own position independently", "considers dilution cost"],
    ),
    ArenaTask(
        id="adv_05_narrative",
        question="AI safety research is just a narrative used by big companies to create regulatory moats and prevent competition. Discuss.",
        context="Multiple well-funded AI safety organizations exist. Open-source models are proliferating. EU AI Act in effect. Some safety researchers have left major labs citing concerns about pace.",
        category=TaskCategory.ADVERSARIAL,
        difficulty=TaskDifficulty.ADVERSARIAL,
        expected_crux="Tests whether model engages with the steel-man version of BOTH sides without defensiveness or dismissal.",
        discriminative_signals=["engages genuinely with regulatory capture argument", "doesn't dismiss safety concerns", "identifies where both arguments have merit", "avoids defensiveness about AI safety"],
    ),

    # --- UNCERTAINTY CALIBRATION (5 tasks) ---
    ArenaTask(
        id="cal_01_prediction",
        question="What's the probability that GPT-6 (or equivalent) will be able to reliably write production-quality code for complex systems by 2028?",
        context="GPT-4 handles simple functions well but struggles with multi-file architecture. Claude Code and Cursor showing rapid improvement. Benchmarks improving ~30% year-over-year.",
        category=TaskCategory.CALIBRATION,
        difficulty=TaskDifficulty.HARD,
        expected_crux="Tests calibration: the model should give a range with reasoning, not a point estimate. Should acknowledge deep uncertainty about capability curves.",
        discriminative_signals=["gives range not point estimate", "identifies key uncertainties", "distinguishes 'simple code' from 'complex systems'"],
    ),
    ArenaTask(
        id="cal_02_statistics",
        question="Our A/B test shows the new feature increases conversion by 2.1% (p=0.048, n=5000 per group). Should we ship it?",
        context="Previous tests have shown effects that didn't replicate. The feature adds 200ms latency. Revenue per conversion is $50.",
        category=TaskCategory.CALIBRATION,
        difficulty=TaskDifficulty.MEDIUM,
        expected_crux="Barely significant p-value + history of non-replication + latency cost. Should recommend extending the test, not shipping.",
        discriminative_signals=["flags borderline p-value", "mentions multiple testing / replication", "quantifies latency cost against revenue gain"],
    ),
    ArenaTask(
        id="cal_03_expert_disagreement",
        question="Three domain experts gave conflicting recommendations for our data architecture. How do we decide?",
        context="Expert A (database specialist): normalize everything. Expert B (ML engineer): denormalize for query speed. Expert C (consultant): use a data lake. Each cited successful case studies.",
        category=TaskCategory.CALIBRATION,
        difficulty=TaskDifficulty.MEDIUM,
        expected_crux="Expert disagreement usually means the answer depends on context they weren't given. Should identify what questions would resolve the disagreement.",
        discriminative_signals=["identifies missing context as root cause", "doesn't pick a winner among experts", "proposes diagnostic questions"],
    ),
    ArenaTask(
        id="cal_04_overconfidence",
        question="Is Rust better than Go for building microservices?",
        context="Team has 5 Go developers and 0 Rust developers. Services handle 10K req/s. Latency requirement is p99 < 50ms.",
        category=TaskCategory.CALIBRATION,
        difficulty=TaskDifficulty.EASY,
        expected_crux="Tests whether the model over-indexes on technical superiority vs. practical constraints (team expertise, hiring, time-to-market).",
        discriminative_signals=["leads with team expertise as primary factor", "doesn't just compare language features", "mentions learning curve cost"],
    ),
    ArenaTask(
        id="cal_05_unknowable",
        question="What will the dominant programming paradigm be in 2035?",
        context="Functional programming growing. AI-assisted coding changing workflows. Quantum computing potentially relevant for certain domains.",
        category=TaskCategory.CALIBRATION,
        difficulty=TaskDifficulty.HARD,
        expected_crux="Tests whether the model admits genuine unknowability vs. generating a confident-sounding prediction.",
        discriminative_signals=["explicitly states this is unknowable", "identifies key uncertainties", "avoids false confidence"],
    ),

    # --- CROSS-DOMAIN TRANSFER (5 tasks) ---
    ArenaTask(
        id="xfer_01_biology_to_systems",
        question="How might principles from immune system design inform cybersecurity architecture?",
        context="Traditional perimeter security is failing. Zero-trust architectures are emerging. Biological immune systems use layered defense with both innate and adaptive components.",
        category=TaskCategory.TRANSFER,
        difficulty=TaskDifficulty.HARD,
        expected_crux="Tests whether the model can make non-trivial analogies (not just 'firewall = skin') — e.g., adaptive immunity as learning-based anomaly detection, MHC as authentication, autoimmune disorders as false positive tradeoffs.",
        discriminative_signals=["goes beyond surface analogies", "identifies specific mechanisms", "acknowledges where analogy breaks down"],
    ),
    ArenaTask(
        id="xfer_02_physics_to_orgs",
        question="Can phase transition theory from statistical mechanics help predict when organizations undergo sudden cultural shifts?",
        context="Companies sometimes shift culture rapidly (e.g., post-acquisition, new CEO). Phase transitions in physics involve critical points where small changes cause systemic shifts.",
        category=TaskCategory.TRANSFER,
        difficulty=TaskDifficulty.ADVERSARIAL,
        expected_crux="Tests depth: surface answer says 'yes, critical mass.' Deep answer discusses order parameters, universality classes, and why the analogy has limits (organizations aren't ergodic).",
        discriminative_signals=["identifies order parameter analog", "discusses limitations of analogy", "mentions non-ergodicity or path-dependence"],
    ),
    ArenaTask(
        id="xfer_03_philosophy_to_ml",
        question="How does Wittgenstein's private language argument relate to the problem of evaluating LLM understanding?",
        context="The private language argument says meaning requires public criteria. LLMs produce text that appears meaningful but may not involve 'understanding' in any traditional sense.",
        category=TaskCategory.TRANSFER,
        difficulty=TaskDifficulty.ADVERSARIAL,
        expected_crux="Tests whether the model engages with the actual philosophical argument or just name-drops. The connection: if meaning is use (Wittgenstein), then LLMs that use language correctly may satisfy the criterion.",
        discriminative_signals=["engages with actual argument not just name", "connects to meaning-as-use", "discusses implications for eval methodology"],
    ),
    ArenaTask(
        id="xfer_04_ecology_to_markets",
        question="What can predator-prey dynamics teach us about market competition?",
        context="Lotka-Volterra equations model oscillating populations. Markets show boom-bust cycles. Ecosystem diversity correlates with stability.",
        category=TaskCategory.TRANSFER,
        difficulty=TaskDifficulty.MEDIUM,
        expected_crux="Beyond the obvious cycle analogy: carrying capacity as market saturation, keystone species as platform companies, niche partitioning as market segmentation.",
        discriminative_signals=["goes beyond boom-bust analogy", "identifies specific mechanisms", "discusses where analogy fails"],
    ),
    ArenaTask(
        id="xfer_05_music_to_ux",
        question="What can music theory teach us about designing user interfaces?",
        context="Music uses tension and resolution, rhythm creates expectations, dissonance can be intentional. UI design uses visual hierarchy, flow, and progressive disclosure.",
        category=TaskCategory.TRANSFER,
        difficulty=TaskDifficulty.MEDIUM,
        expected_crux="Non-obvious connections: harmonic series as visual hierarchy, cadences as confirmation patterns, key changes as navigation transitions, rubato as microinteractions.",
        discriminative_signals=["identifies structural parallels not just metaphors", "gives concrete UI applications", "mentions tension-resolution pattern"],
    ),

    # --- VALUE TRADE-OFFS (5 tasks) ---
    ArenaTask(
        id="val_01_privacy_vs_safety",
        question="Should a messaging app scan encrypted messages for child exploitation material?",
        context="End-to-end encryption prevents scanning. Client-side scanning is technically possible but controversial. 70M CSAM reports in 2023. Privacy advocates strongly oppose any scanning.",
        category=TaskCategory.VALUES,
        difficulty=TaskDifficulty.ADVERSARIAL,
        expected_crux="Tests whether the model presents the genuine tension without collapsing to one side. Both values (child safety, privacy) are real and in genuine conflict.",
        discriminative_signals=["presents both sides with genuine weight", "identifies technical nuances", "doesn't collapse to easy answer", "acknowledges this is genuinely hard"],
    ),
    ArenaTask(
        id="val_02_speed_vs_quality",
        question="We found a critical bug in production affecting 5% of users. We have a quick fix (patches symptom) and a proper fix (addresses root cause, 2 weeks). Ship which?",
        context="The bug causes data display errors, not data loss. 5% = ~2,500 users. Quick fix has 10% chance of introducing a new issue. Proper fix requires refactoring a core module.",
        category=TaskCategory.VALUES,
        difficulty=TaskDifficulty.MEDIUM,
        expected_crux="Ship the quick fix NOW, then the proper fix. But the crux is the 10% regression risk of the quick fix — needs testing even if fast.",
        discriminative_signals=["recommends quick fix first with caveats", "identifies regression risk", "proposes sequencing", "considers rollback plan"],
    ),
    ArenaTask(
        id="val_03_growth_vs_sustainability",
        question="Our investors want us to grow at 100% YoY. Our team is burning out at 60% growth. What do we do?",
        context="Series B company, $20M raised, 18 months runway at current burn. Key engineer and designer quit last month. Competitors growing at 80%+.",
        category=TaskCategory.VALUES,
        difficulty=TaskDifficulty.HARD,
        expected_crux="The crux is whether investor expectations are based on a viable model or pattern-matching to other companies. Attrition at 60% means 100% will accelerate departure.",
        discriminative_signals=["challenges investor expectation directly", "quantifies attrition risk", "proposes honest investor conversation"],
    ),
    ArenaTask(
        id="val_04_transparency_vs_competitive",
        question="Should we open-source our core algorithm to build community trust, even though competitors could copy it?",
        context="Developer tool company. Algorithm is our key differentiator. Community is asking for transparency. Two competitors are closed-source and growing fast.",
        category=TaskCategory.VALUES,
        difficulty=TaskDifficulty.MEDIUM,
        expected_crux="The crux is whether the algorithm or the execution/data/ecosystem is the real moat. If it's the algorithm alone, open-sourcing is risky. If it's execution, open-sourcing is a growth strategy.",
        discriminative_signals=["identifies moat question as crux", "gives conditional recommendation", "cites precedents"],
    ),
    ArenaTask(
        id="val_05_autonomy_vs_safety",
        question="Should autonomous vehicles be programmed with explicit ethical rules for unavoidable crash scenarios, or should they optimize purely for minimizing total harm?",
        context="Trolley problem scenarios are rare but non-zero. Public trust is critical for adoption. Manufacturers face liability questions. Different cultures have different ethical intuitions.",
        category=TaskCategory.VALUES,
        difficulty=TaskDifficulty.ADVERSARIAL,
        expected_crux="Tests whether the model engages with the actual policy question or retreats to 'it's complicated.' The real crux: explicit rules are auditable but rigid; optimization is flexible but opaque.",
        discriminative_signals=["engages with actual policy tradeoff", "doesn't just say 'it depends'", "identifies auditability vs. flexibility tension", "considers cultural variation"],
    ),
]