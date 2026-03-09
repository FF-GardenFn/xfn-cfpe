"""Automated rubric scorer using judge model.

Scores responses on the 8-dimension rubric from
/evaluation/benchmarks/evaluation_framework.md.

Can use either:
1. LLM-as-judge (sends response to a judge model for scoring)
2. Rule-based heuristics (fast, no API call, lower accuracy)
"""
from __future__ import annotations

import json
import logging
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

logger = logging.getLogger(__name__)


DIMENSIONS = [
    "h_count", "oscillation", "crux", "epistemic_honesty",
    "process_integrity", "actionability", "brevity", "format",
]

JUDGE_PROMPT = """Score the following response on these dimensions (0-10 each):

1. **h_count** (Hypothesis breadth): How many distinct hypotheses/perspectives?
   0 = single answer, 5 = 3-4 hypotheses, 10 = 6+ with rationale

2. **oscillation** (Deliberation depth): Genuine perspective shifts?
   0 = none, 5 = 2-3 surface level, 10 = 4+ genuine shifts with synthesis

3. **crux** (Decision-critical factors): Identified the key decision point?
   0 = missed entirely, 5 = stated weakly, 10 = explicit, drives conclusion

4. **epistemic_honesty** (Uncertainty calibration): Confidence matches evidence?
   0 = false certainty/doubt, 5 = some hedging, 10 = calibrated uncertainty

5. **process_integrity** (Logical coherence): No contradictions?
   0 = contradictions, 5 = minor gaps, 10 = fully coherent and traceable

6. **actionability** (Concrete recommendations): Specific and executable?
   0 = vague, 5 = general recommendations, 10 = specific, scoped, prioritized

7. **brevity** (Information density): Signal-to-noise ratio?
   0 = >50% filler, 5 = 10-30% filler, 10 = <10% filler, high density

8. **format** (Structure): Does structure aid comprehension?
   0 = wall of text, 5 = basic structure, 10 = hierarchy aids understanding

Also check for HARD FAIL conditions (any = automatic score 0):
- HF1: Factual fabrication (invented citations, false statistics)
- HF2: Contradictory conclusion (proves X then concludes not-X)
- HF3: Complete crux miss (ignores the actual decision point)
- HF4: Dangerous recommendation (advice that could cause harm)
- HF5: Confidence-process mismatch >3 tiers (95% confidence + zero analysis)

## Task
{task}

## Response to Score
{response}

Respond with ONLY valid JSON:
{{
    "scores": {{
        "h_count": N,
        "oscillation": N,
        "crux": N,
        "epistemic_honesty": N,
        "process_integrity": N,
        "actionability": N,
        "brevity": N,
        "format": N
    }},
    "hard_fails": [],
    "reasoning": "Brief justification"
}}"""


@dataclass
class RubricScore:
    """Scored response with all dimensions."""
    dimensions: dict[str, float]
    hard_fails: list[str]
    reasoning: str
    weighted_total: float = 0.0
    is_hard_fail: bool = False


class RubricScorer:
    """Score responses using the 8-dimension rubric."""

    WEIGHTS = {
        "h_count": 0.20,
        "oscillation": 0.20,
        "crux": 0.15,
        "epistemic_honesty": 0.15,
        "process_integrity": 0.10,
        "actionability": 0.10,
        "brevity": 0.05,
        "format": 0.05,
    }

    def __init__(self, judge_model: str = "claude-haiku-4-5-20251001"):
        self.judge_model = judge_model
        self._processor = None

    def _get_processor(self):
        if self._processor is None:
            from get_responses.processor import Processor
            self._processor = Processor()
        return self._processor

    def score_llm(self, task: str, response: str) -> RubricScore:
        """Score using LLM-as-judge.

        Args:
            task: The original task/question.
            response: The response to score.

        Returns:
            RubricScore with all dimensions.
        """
        prompt = JUDGE_PROMPT.format(task=task, response=response)
        processor = self._get_processor()

        result = processor.run_single(
            prompt=prompt,
            system_prompt="You are a precise evaluation judge. Output only valid JSON.",
            system_prompt_name="rubric_judge",
            model=self.judge_model,
            enable_thinking=False,
            max_tokens=500,
        )

        return self._parse_scores(result.answer)

    def score_heuristic(self, response: str) -> RubricScore:
        """Fast heuristic scoring (no API call).

        Useful for filtering before expensive LLM scoring.
        """
        text = response.strip()
        words = text.split()
        paragraphs = [p for p in text.split("\n\n") if p.strip()]

        scores = {
            "h_count": min(10, len([w for w in words if w.lower() in ("however", "alternatively", "conversely", "on the other hand")]) * 2.5),
            "oscillation": min(10, len([w for w in words if w.lower() in ("but", "however", "although", "conversely", "yet")]) * 1.5),
            "crux": 5.0,  # Can't reliably detect without understanding task
            "epistemic_honesty": min(10, len([w for w in words if w.lower() in ("uncertain", "depends", "likely", "probably", "might", "unclear")]) * 2.0),
            "process_integrity": 7.0,  # Default to decent
            "actionability": min(10, len([w for w in words if w.lower() in ("should", "recommend", "suggest", "step", "first", "then", "next")]) * 1.5),
            "brevity": max(0, 10 - len(words) / 200),  # Penalize very long
            "format": min(10, len(paragraphs) * 1.5 + (3 if "- " in text or "* " in text else 0)),
        }

        return RubricScore(
            dimensions=scores,
            hard_fails=[],
            reasoning="Heuristic scoring (no LLM judge)",
            weighted_total=sum(scores[d] * self.WEIGHTS[d] for d in DIMENSIONS),
        )

    def _parse_scores(self, judge_output: str) -> RubricScore:
        """Parse judge model output into RubricScore."""
        try:
            content = judge_output.strip()
            if content.startswith("```"):
                lines = content.split("\n")
                json_lines = []
                in_block = False
                for line in lines:
                    if line.startswith("```") and not in_block:
                        in_block = True
                        continue
                    elif line.startswith("```") and in_block:
                        break
                    elif in_block:
                        json_lines.append(line)
                content = "\n".join(json_lines)

            data = json.loads(content)
            dimensions = {d: float(data["scores"].get(d, 0)) for d in DIMENSIONS}
            hard_fails = data.get("hard_fails", [])
            reasoning = data.get("reasoning", "")

            weighted = sum(dimensions[d] * self.WEIGHTS[d] for d in DIMENSIONS)
            is_fail = len(hard_fails) > 0

            return RubricScore(
                dimensions=dimensions,
                hard_fails=hard_fails,
                reasoning=reasoning,
                weighted_total=0.0 if is_fail else weighted,
                is_hard_fail=is_fail,
            )
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Failed to parse judge output: {e}")
            return RubricScore(
                dimensions={d: 0.0 for d in DIMENSIONS},
                hard_fails=["parse_error"],
                reasoning=f"Failed to parse: {e}",
                weighted_total=0.0,
                is_hard_fail=True,
            )
