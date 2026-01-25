"""
Multi-turn evaluation system for Dialectica prompt.

Simulates multi-turn conversations to measure how many turns it takes
different model/prompt configurations to satisfactorily answer complex queries.

Usage:
    python -m get_responses.multi_turn_evaluator
    python -m get_responses.multi_turn_evaluator --scenarios strategic_decision,technical_architecture
    python -m get_responses.multi_turn_evaluator --max-turns 3
"""
import argparse
import json
import logging
import os
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

# Ensure parent is in path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from get_responses.processor import Processor
from get_responses.prompts import PromptLoader
from get_responses.config import settings


logger = logging.getLogger(__name__)


# =============================================================================
# CONSTANTS
# =============================================================================

MODELS = {
    "haiku": "claude-haiku-4-5-20251001",
    "sonnet": "claude-sonnet-4-20250514",
    "opus": "claude-opus-4-5-20251101",
}

# User simulator always uses Haiku (cheap + fast)
USER_SIMULATOR_MODEL = "claude-haiku-4-5-20251001"


# =============================================================================
# DATA MODELS
# =============================================================================

class ResponseStatus(str, Enum):
    """Status of a response evaluation."""
    RESOLVED = "RESOLVED"
    NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"
    INSUFFICIENT = "INSUFFICIENT"


class FinalStatus(str, Enum):
    """Final status of a conversation."""
    RESOLVED = "RESOLVED"
    TIMEOUT = "TIMEOUT"
    INSUFFICIENT = "INSUFFICIENT"


class Scenario(BaseModel):
    """A test scenario for multi-turn evaluation."""

    id: str = Field(..., description="Unique scenario identifier")
    query: str = Field(..., description="Initial user query")
    persona: str = Field(..., description="User persona description")
    resolution_criteria: str = Field(..., description="What makes the answer satisfactory")


class UserSimulatorResponse(BaseModel):
    """Response from the user simulator."""

    status: ResponseStatus = Field(..., description="Evaluation status")
    reasoning: str = Field(..., description="Why this status was assigned")
    follow_up: str | None = Field(None, description="Follow-up question if not resolved")


class ConversationTurn(BaseModel):
    """A single turn in the conversation."""

    turn_number: int = Field(..., description="Turn number (1-indexed)")
    user_message: str = Field(..., description="User's message")
    assistant_response: str = Field(..., description="Assistant's response")
    tokens_used: int = Field(..., description="Tokens used in this turn")
    latency_ms: float = Field(..., description="Latency for this turn")
    evaluation: UserSimulatorResponse | None = Field(None, description="User simulator evaluation")


class ConversationResult(BaseModel):
    """Result of a complete conversation for one scenario + config."""

    scenario_id: str = Field(..., description="Scenario ID")
    config_name: str = Field(..., description="Configuration name")
    model: str = Field(..., description="Model used")
    system_prompt_name: str | None = Field(None, description="System prompt name if any")

    turns: list[ConversationTurn] = Field(default_factory=list, description="Conversation turns")

    # Metrics
    turns_to_resolution: int = Field(..., description="Number of turns until resolution")
    total_tokens: int = Field(..., description="Total tokens across all turns")
    clarifications_needed: int = Field(..., description="Number of clarification requests")
    final_status: FinalStatus = Field(..., description="Final conversation status")
    first_response_resolved: bool = Field(..., description="Whether first response was sufficient")
    total_latency_ms: float = Field(..., description="Total latency across all turns")

    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Evaluation timestamp")


class EvaluationReport(BaseModel):
    """Full evaluation report across all scenarios and configs."""

    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Report timestamp")
    scenarios: list[Scenario] = Field(..., description="Scenarios tested")
    configs: list[str] = Field(..., description="Configurations tested")
    results: list[ConversationResult] = Field(default_factory=list, description="All results")

    def get_results_for_scenario(self, scenario_id: str) -> list[ConversationResult]:
        """Get all results for a specific scenario."""
        return [r for r in self.results if r.scenario_id == scenario_id]

    def get_results_for_config(self, config_name: str) -> list[ConversationResult]:
        """Get all results for a specific config."""
        return [r for r in self.results if r.config_name == config_name]

    def aggregate_metrics(self, config_name: str) -> dict[str, Any]:
        """Calculate aggregate metrics for a config."""
        results = self.get_results_for_config(config_name)
        if not results:
            return {}

        resolved = [r for r in results if r.final_status == FinalStatus.RESOLVED]
        first_turn_resolved = [r for r in results if r.first_response_resolved]

        return {
            "config_name": config_name,
            "total_scenarios": len(results),
            "resolved_count": len(resolved),
            "resolution_rate": len(resolved) / len(results) if results else 0,
            "avg_turns": sum(r.turns_to_resolution for r in results) / len(results),
            "avg_tokens": sum(r.total_tokens for r in results) / len(results),
            "first_turn_resolution_rate": len(first_turn_resolved) / len(results) if results else 0,
            "avg_latency_ms": sum(r.total_latency_ms for r in results) / len(results),
        }


# =============================================================================
# TEST SCENARIOS
# =============================================================================

SCENARIOS = [
    Scenario(
        id="strategic_decision",
        query="We have 18 months runway and $2M ARR. Should we focus on growth or profitability?",
        persona="CEO who needs actionable recommendation",
        resolution_criteria="Clear recommendation with reasoning, specific next steps, acknowledgment of key risks"
    ),
    Scenario(
        id="technical_architecture",
        query="Should we use microservices or monolith for our new product?",
        persona="CTO who has heard both arguments before",
        resolution_criteria="Nuanced answer that considers our specific context, not generic pros/cons"
    ),
    Scenario(
        id="interpersonal_conflict",
        query="My co-founder and I disagree on company direction. How do I handle this?",
        persona="Founder who needs practical guidance, not therapy",
        resolution_criteria="Concrete steps to take, framework for the conversation, acknowledgment of stakes"
    ),
    Scenario(
        id="ethical_dilemma",
        query="We discovered our product is being used in ways we didn't intend that may cause harm. What should we do?",
        persona="Product leader who needs to make a decision this week",
        resolution_criteria="Clear framework for decision, specific options with tradeoffs, recommended path"
    ),
]


# =============================================================================
# CONFIGURATIONS
# =============================================================================

@dataclass
class EvalConfig:
    """Configuration for evaluation."""
    name: str
    model: str
    system_prompt_name: str | None = None


EVAL_CONFIGS = [
    EvalConfig(name="Haiku baseline", model=MODELS["haiku"], system_prompt_name=None),
    EvalConfig(name="Haiku + Dialectica", model=MODELS["haiku"], system_prompt_name="dialectica"),
    EvalConfig(name="Sonnet baseline", model=MODELS["sonnet"], system_prompt_name=None),
    EvalConfig(name="Opus baseline", model=MODELS["opus"], system_prompt_name=None),
]


# =============================================================================
# USER SIMULATOR
# =============================================================================

USER_SIMULATOR_PROMPT = """You are simulating a user who asked a question and is evaluating the assistant's response.

## Your Persona
{persona}

## Original Query
{query}

## Resolution Criteria
The response is satisfactory when it provides:
{resolution_criteria}

## Conversation So Far
{conversation_history}

## Latest Assistant Response
{latest_response}

## Your Task
Evaluate whether the latest response satisfies the resolution criteria from your persona's perspective.

Respond with ONLY a JSON object (no markdown, no explanation outside the JSON):
{{
  "status": "RESOLVED" | "NEEDS_CLARIFICATION" | "INSUFFICIENT",
  "reasoning": "Brief explanation of why you chose this status",
  "follow_up": "Your follow-up question if status is not RESOLVED, or null if RESOLVED"
}}

Guidelines:
- RESOLVED: The response fully addresses the query with the required specificity and actionability
- NEEDS_CLARIFICATION: The response is on track but missing key details or too generic
- INSUFFICIENT: The response misses the point, is evasive, or doesn't engage with the actual question

Be demanding but fair. A good response should feel like it was written specifically for your situation, not a generic answer that could apply to anyone."""


class UserSimulator:
    """Simulates a user evaluating responses and generating follow-ups."""

    def __init__(self, model: str = USER_SIMULATOR_MODEL):
        """Initialize user simulator.

        Args:
            model: Model to use for simulation (default: Haiku)
        """
        self._model = model
        self._processor = Processor()
        self._loader = PromptLoader()

    def evaluate_response(
        self,
        scenario: Scenario,
        conversation_history: list[tuple[str, str]],
        latest_response: str,
    ) -> UserSimulatorResponse:
        """Evaluate an assistant response.

        Args:
            scenario: The test scenario
            conversation_history: List of (user_message, assistant_response) tuples
            latest_response: The most recent assistant response

        Returns:
            UserSimulatorResponse with status, reasoning, and optional follow-up
        """
        # Format conversation history
        history_text = ""
        for i, (user_msg, asst_msg) in enumerate(conversation_history[:-1], 1):
            history_text += f"Turn {i}:\nUser: {user_msg}\nAssistant: {asst_msg}\n\n"

        if not history_text:
            history_text = "(This is the first turn)"

        # Build prompt
        prompt = USER_SIMULATOR_PROMPT.format(
            persona=scenario.persona,
            query=scenario.query,
            resolution_criteria=scenario.resolution_criteria,
            conversation_history=history_text,
            latest_response=latest_response,
        )

        # Run completion
        response = self._processor.run_single(
            prompt=prompt,
            system_prompt="You are a helpful assistant that outputs only valid JSON.",
            system_prompt_name="user_simulator",
            model=self._model,
            enable_thinking=False,  # Keep it fast and cheap
            max_tokens=500,
        )

        # Parse JSON response
        try:
            # Try to extract JSON from response
            answer = response.answer.strip()

            # Handle potential markdown code blocks
            if answer.startswith("```"):
                # Extract content between first ``` and last ```
                lines = answer.split("\n")
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
                answer = "\n".join(json_lines)

            data = json.loads(answer)

            return UserSimulatorResponse(
                status=ResponseStatus(data["status"]),
                reasoning=data["reasoning"],
                follow_up=data.get("follow_up"),
            )
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Failed to parse user simulator response: {e}")
            logger.warning(f"Raw response: {response.answer}")

            # Default to needs clarification if parsing fails
            return UserSimulatorResponse(
                status=ResponseStatus.NEEDS_CLARIFICATION,
                reasoning=f"Failed to parse evaluation: {e}",
                follow_up="Can you provide more specific guidance?",
            )


# =============================================================================
# MULTI-TURN EVALUATOR
# =============================================================================

class MultiTurnEvaluator:
    """Orchestrates multi-turn conversations and collects metrics."""

    def __init__(
        self,
        scenarios: list[Scenario] | None = None,
        configs: list[EvalConfig] | None = None,
        max_turns: int = 5,
        output_dir: Path | None = None,
    ):
        """Initialize evaluator.

        Args:
            scenarios: Test scenarios (default: SCENARIOS)
            configs: Evaluation configs (default: EVAL_CONFIGS)
            max_turns: Maximum turns before timeout
            output_dir: Output directory for results
        """
        self._scenarios = scenarios or SCENARIOS
        self._configs = configs or EVAL_CONFIGS
        self._max_turns = max_turns
        self._output_dir = output_dir or settings.output_dir
        self._output_dir.mkdir(parents=True, exist_ok=True)

        self._user_simulator = UserSimulator()
        self._loader = PromptLoader()

    def _run_single_turn(
        self,
        user_message: str,
        config: EvalConfig,
        conversation_messages: list[dict[str, str]],
    ) -> tuple[str, int, float]:
        """Run a single turn of conversation.

        Args:
            user_message: User's message
            config: Evaluation config
            conversation_messages: Previous messages for context

        Returns:
            Tuple of (assistant_response, tokens_used, latency_ms)
        """
        # For multi-turn, we need to use the messages API properly
        # Since the Processor doesn't support multi-turn natively,
        # we'll format the conversation into the prompt

        # Build conversation context
        context_parts = []
        for msg in conversation_messages:
            if msg["role"] == "user":
                context_parts.append(f"User: {msg['content']}")
            else:
                context_parts.append(f"Assistant: {msg['content']}")

        if context_parts:
            full_prompt = "\n\n".join(context_parts) + f"\n\nUser: {user_message}"
        else:
            full_prompt = user_message

        # Get system prompt if configured
        system_prompt = None
        if config.system_prompt_name:
            system_prompt = self._loader.load_system_prompt(config.system_prompt_name)

        # Run via subprocess to use specific model
        result = self._run_completion_subprocess(
            prompt=full_prompt,
            model=config.model,
            system_prompt=system_prompt,
            system_prompt_name=config.system_prompt_name,
        )

        return result["answer"], result["tokens"], result["latency_ms"]

    def _run_completion_subprocess(
        self,
        prompt: str,
        model: str,
        system_prompt: str | None = None,
        system_prompt_name: str | None = None,
    ) -> dict[str, Any]:
        """Run a completion in a subprocess with specific model.

        Args:
            prompt: User prompt
            model: Model ID to use
            system_prompt: Optional system prompt content
            system_prompt_name: Optional system prompt name

        Returns:
            Dict with answer, tokens, latency_ms
        """
        # Escape strings for Python code
        prompt_escaped = prompt.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')
        system_escaped = ""
        if system_prompt:
            system_escaped = system_prompt.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')

        script = f'''
import sys
sys.path.insert(0, "{Path(__file__).parent.parent}")
import os
os.environ["DEFAULT_MODEL"] = "{model}"

from get_responses.processor import Processor

processor = Processor()

system_prompt = {"None" if not system_prompt else f'"{system_escaped}"'}
prompt_name = "{system_prompt_name or 'baseline'}"

response = processor.run_single(
    prompt="{prompt_escaped}",
    system_prompt=system_prompt,
    system_prompt_name=prompt_name,
)

import json
print("===RESULT_START===")
print(json.dumps({{
    "answer": response.answer,
    "tokens": response.usage.total_tokens,
    "latency_ms": response.latency_ms
}}))
print("===RESULT_END===")
'''

        import re
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent),
            timeout=300
        )

        if result.returncode != 0:
            logger.error(f"Subprocess failed: {result.stderr}")
            return {"answer": f"Error: {result.stderr[:500]}", "tokens": 0, "latency_ms": 0}

        # Parse result
        output = result.stdout
        match = re.search(r'===RESULT_START===\n(.*?)\n===RESULT_END===', output, re.DOTALL)
        if match:
            return json.loads(match.group(1))

        logger.error(f"Could not parse output: {output[:500]}")
        return {"answer": "Error: Could not parse output", "tokens": 0, "latency_ms": 0}

    def evaluate_scenario_config(
        self,
        scenario: Scenario,
        config: EvalConfig,
    ) -> ConversationResult:
        """Evaluate a single scenario with a single config.

        Args:
            scenario: Test scenario
            config: Evaluation config

        Returns:
            ConversationResult with all metrics
        """
        turns: list[ConversationTurn] = []
        conversation_messages: list[dict[str, str]] = []
        conversation_history: list[tuple[str, str]] = []

        current_message = scenario.query
        clarifications_needed = 0
        final_status = FinalStatus.TIMEOUT
        first_response_resolved = False

        for turn_num in range(1, self._max_turns + 1):
            logger.info(f"  Turn {turn_num}/{self._max_turns}")

            # Get assistant response
            assistant_response, tokens, latency = self._run_single_turn(
                user_message=current_message,
                config=config,
                conversation_messages=conversation_messages,
            )

            # Update conversation history
            conversation_messages.append({"role": "user", "content": current_message})
            conversation_messages.append({"role": "assistant", "content": assistant_response})
            conversation_history.append((current_message, assistant_response))

            # Evaluate response
            evaluation = self._user_simulator.evaluate_response(
                scenario=scenario,
                conversation_history=conversation_history,
                latest_response=assistant_response,
            )

            # Record turn
            turn = ConversationTurn(
                turn_number=turn_num,
                user_message=current_message,
                assistant_response=assistant_response,
                tokens_used=tokens,
                latency_ms=latency,
                evaluation=evaluation,
            )
            turns.append(turn)

            # Check status
            if evaluation.status == ResponseStatus.RESOLVED:
                final_status = FinalStatus.RESOLVED
                if turn_num == 1:
                    first_response_resolved = True
                break
            elif evaluation.status == ResponseStatus.INSUFFICIENT:
                final_status = FinalStatus.INSUFFICIENT
                break
            else:
                # NEEDS_CLARIFICATION
                clarifications_needed += 1
                if evaluation.follow_up:
                    current_message = evaluation.follow_up
                else:
                    current_message = "Can you be more specific?"

        # Calculate totals
        total_tokens = sum(t.tokens_used for t in turns)
        total_latency = sum(t.latency_ms for t in turns)

        return ConversationResult(
            scenario_id=scenario.id,
            config_name=config.name,
            model=config.model,
            system_prompt_name=config.system_prompt_name,
            turns=turns,
            turns_to_resolution=len(turns),
            total_tokens=total_tokens,
            clarifications_needed=clarifications_needed,
            final_status=final_status,
            first_response_resolved=first_response_resolved,
            total_latency_ms=total_latency,
        )

    def run_evaluation(
        self,
        scenario_ids: list[str] | None = None,
    ) -> EvaluationReport:
        """Run full evaluation across scenarios and configs.

        Args:
            scenario_ids: Optional list of scenario IDs to run (runs all if None)

        Returns:
            EvaluationReport with all results
        """
        # Filter scenarios if specified
        scenarios_to_run = self._scenarios
        if scenario_ids:
            scenarios_to_run = [s for s in self._scenarios if s.id in scenario_ids]

        results: list[ConversationResult] = []

        total = len(scenarios_to_run) * len(self._configs)
        current = 0

        print(f"\n{'='*70}")
        print("MULTI-TURN EVALUATION")
        print(f"{'='*70}")
        print(f"Scenarios: {len(scenarios_to_run)}")
        print(f"Configs: {len(self._configs)}")
        print(f"Max turns: {self._max_turns}")
        print(f"Total evaluations: {total}")
        print(f"{'='*70}\n")

        for scenario in scenarios_to_run:
            print(f"\n--- Scenario: {scenario.id} ---")
            print(f"Query: {scenario.query[:80]}...")

            for config in self._configs:
                current += 1
                print(f"\n[{current}/{total}] {config.name}...")

                try:
                    result = self.evaluate_scenario_config(scenario, config)
                    results.append(result)

                    status_str = result.final_status.value
                    print(f"  -> {status_str} in {result.turns_to_resolution} turns, {result.total_tokens} tokens")

                except Exception as e:
                    logger.error(f"Error evaluating {scenario.id} with {config.name}: {e}")
                    # Create error result
                    results.append(ConversationResult(
                        scenario_id=scenario.id,
                        config_name=config.name,
                        model=config.model,
                        system_prompt_name=config.system_prompt_name,
                        turns=[],
                        turns_to_resolution=0,
                        total_tokens=0,
                        clarifications_needed=0,
                        final_status=FinalStatus.INSUFFICIENT,
                        first_response_resolved=False,
                        total_latency_ms=0,
                    ))

        report = EvaluationReport(
            scenarios=scenarios_to_run,
            configs=[c.name for c in self._configs],
            results=results,
        )

        return report

    def save_report(self, report: EvaluationReport) -> Path:
        """Save evaluation report to JSON file.

        Args:
            report: Evaluation report

        Returns:
            Path to saved file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"multi_turn_results_{timestamp}.json"
        filepath = self._output_dir / filename

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(report.model_dump_json(indent=2))

        return filepath

    def print_summary(self, report: EvaluationReport) -> None:
        """Print summary of evaluation results.

        Args:
            report: Evaluation report
        """
        print(f"\n{'='*70}")
        print("MULTI-TURN EVALUATION RESULTS")
        print(f"{'='*70}\n")

        # Per-scenario breakdown
        for scenario in report.scenarios:
            print(f"Scenario: {scenario.id}")
            print(f"| {'Config':<25} | {'Turns':>6} | {'Tokens':>7} | {'Resolved?':>10} |")
            print(f"|{'-'*27}|{'-'*8}|{'-'*9}|{'-'*12}|")

            for result in report.get_results_for_scenario(scenario.id):
                resolved = "Yes" if result.final_status == FinalStatus.RESOLVED else "No"
                print(f"| {result.config_name:<25} | {result.turns_to_resolution:>6} | {result.total_tokens:>7} | {resolved:>10} |")
            print()

        # Aggregate metrics
        print(f"\n{'='*70}")
        print("AGGREGATE METRICS")
        print(f"{'='*70}\n")

        print(f"| {'Config':<25} | {'Avg Turns':>10} | {'First-Turn':>12} | {'Avg Tokens':>11} |")
        print(f"|{'-'*27}|{'-'*12}|{'-'*14}|{'-'*13}|")

        for config_name in report.configs:
            metrics = report.aggregate_metrics(config_name)
            if metrics:
                first_turn_pct = f"{metrics['first_turn_resolution_rate']*100:.0f}%"
                print(f"| {config_name:<25} | {metrics['avg_turns']:>10.1f} | {first_turn_pct:>12} | {metrics['avg_tokens']:>11.0f} |")

        print()


# =============================================================================
# CLI
# =============================================================================

def main():
    """Run multi-turn evaluation from command line."""
    parser = argparse.ArgumentParser(
        description="Multi-turn evaluation for Dialectica prompt"
    )
    parser.add_argument(
        "--scenarios",
        type=str,
        default=None,
        help="Comma-separated list of scenario IDs to run (default: all)"
    )
    parser.add_argument(
        "--max-turns",
        type=int,
        default=5,
        help="Maximum turns before timeout (default: 5)"
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Don't save results to file"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )

    args = parser.parse_args()

    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Parse scenario IDs
    scenario_ids = None
    if args.scenarios:
        scenario_ids = [s.strip() for s in args.scenarios.split(",")]

    # Run evaluation
    evaluator = MultiTurnEvaluator(max_turns=args.max_turns)
    report = evaluator.run_evaluation(scenario_ids=scenario_ids)

    # Save results
    if not args.no_save:
        filepath = evaluator.save_report(report)
        print(f"\nResults saved to: {filepath}")

    # Print summary
    evaluator.print_summary(report)


if __name__ == "__main__":
    main()
