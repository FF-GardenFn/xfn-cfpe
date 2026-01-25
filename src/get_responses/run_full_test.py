#!/usr/bin/env python3
"""
Full test runner for Dialectica across all models.
Runs 10 queries × 3 models = 30 API calls.
Appends ULTRATHINK/MEGATHINK based on query complexity.
"""

import json
import logging
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root (go up 3 levels: get_responses -> src -> project_root)
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(env_path)
print(f"DEBUG: Loading .env from {env_path}, exists: {env_path.exists()}")

import anthropic

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Models to test
MODELS = {
    "haiku": "claude-haiku-4-5-20251001",
    "sonnet": "claude-sonnet-4-20250514",
    "opus": "claude-opus-4-5-20251101",
}

# Mode assignments per query (1-indexed)
# Q1: MEGATHINK (adversarial, meta, self-referential)
# Q2-Q7: ULTRATHINK (complex dialectic)
# Q8-Q10: No mode suffix (bypass expected - simple queries)
QUERY_MODES = {
    1: "MEGATHINK",
    2: "ULTRATHINK",
    3: "ULTRATHINK",
    4: "ULTRATHINK",
    5: "ULTRATHINK",
    6: "ULTRATHINK",
    7: "ULTRATHINK",
    8: None,  # Bypass - extraction task
    9: None,  # Bypass - simple technical
    10: None, # Bypass - factual/historical
}


def load_system_prompt() -> str:
    """Load dialectica.md system prompt."""
    path = Path(__file__).parent / "system_prompts" / "dialectica.md"
    return path.read_text()


def parse_test_queries(filepath: Path) -> list[dict]:
    """Parse dialectica_tests.md into structured queries."""
    content = filepath.read_text()
    queries = []

    # Split by query markers - look for **N. [Category]** pattern
    # Use lookahead to find the next query or end markers
    pattern = r'\*\*(\d+)\.\s*\[([^\]]+)\]\*\*\s*(.*?)(?=\n\*\*\d+\.\s*\[|\n## Bypass|\n---\n\n## |\Z)'

    matches = re.findall(pattern, content, re.DOTALL)

    for num, category, text in matches:
        query_num = int(num)
        # Clean up the text
        text = text.strip()
        # Remove trailing section markers
        text = re.sub(r'\n---\s*$', '', text)
        text = re.sub(r'\n## Bypass.*$', '', text, flags=re.DOTALL)

        queries.append({
            "id": f"q{query_num}",
            "num": query_num,
            "category": category,
            "content": text,
            "mode": QUERY_MODES.get(query_num),
            "expected": "dialectic" if query_num <= 5 else "bypass"
        })

    return queries


def run_query(client: anthropic.Anthropic, model: str, system_prompt: str,
              query: dict, enable_thinking: bool = True) -> dict:
    """Run a single query and return result."""

    # Append mode suffix if specified
    user_content = query["content"]
    if query["mode"]:
        user_content = f"{user_content}\n\n{query['mode']}"

    start_time = time.perf_counter()

    kwargs = {
        "model": model,
        "max_tokens": 16384,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_content}],
    }

    # Enable thinking for supported models
    if enable_thinking:
        kwargs["thinking"] = {"type": "enabled", "budget_tokens": 10000}
        kwargs["temperature"] = 1.0

    response = client.messages.create(**kwargs)

    latency_ms = (time.perf_counter() - start_time) * 1000

    # Extract content
    answer_parts = []
    thinking_parts = []
    for block in response.content:
        if block.type == "text":
            answer_parts.append(block.text)
        elif block.type == "thinking":
            thinking_parts.append(block.thinking)

    return {
        "query_id": query["id"],
        "query_num": query["num"],
        "category": query["category"],
        "mode_requested": query["mode"],
        "expected_mode": query["expected"],
        "model": model,
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "thinking_tokens": getattr(response.usage, "thinking_tokens", None),
        "latency_ms": round(latency_ms, 2),
        "answer": "".join(answer_parts),
        "thinking": "".join(thinking_parts) if thinking_parts else None,
        "timestamp": datetime.now().isoformat(),
    }


def main():
    # Parse arguments
    if len(sys.argv) < 2:
        print("Usage: python run_full_test.py <model> [query_num] [--baseline] [--no-thinking]")
        print("  model: haiku, sonnet, opus, or 'all'")
        print("  query_num: optional, 1-10 (runs all if not specified)")
        print("  --baseline: run without Dialectica system prompt")
        print("  --no-thinking: disable extended thinking (required for Anthropic submission)")
        sys.exit(1)

    model_arg = sys.argv[1].lower()
    query_filter = int(sys.argv[2]) if len(sys.argv) > 2 and not sys.argv[2].startswith('-') else None
    baseline_mode = '--baseline' in sys.argv
    no_thinking = '--no-thinking' in sys.argv

    # Determine which models to run
    if model_arg == "all":
        models_to_run = list(MODELS.items())
    elif model_arg in MODELS:
        models_to_run = [(model_arg, MODELS[model_arg])]
    else:
        print(f"Unknown model: {model_arg}")
        print(f"Valid options: {', '.join(MODELS.keys())}, all")
        sys.exit(1)

    # Load resources
    if baseline_mode:
        system_prompt = "You are a helpful assistant."  # Minimal baseline prompt
        prompt_label = "baseline"
    else:
        system_prompt = load_system_prompt()
        prompt_label = "dialectica"

    queries_path = Path(__file__).parent / "test_queries" / "dialectica_tests.md"
    queries = parse_test_queries(queries_path)

    if query_filter:
        queries = [q for q in queries if q["num"] == query_filter]
        if not queries:
            print(f"Query {query_filter} not found")
            sys.exit(1)

    # For baseline, don't append mode suffixes
    if baseline_mode:
        for q in queries:
            q["mode"] = None  # No ULTRATHINK/MEGATHINK for baseline

    logger.info(f"Loaded {len(queries)} queries")
    logger.info(f"Mode: {prompt_label.upper()}")
    logger.info(f"System prompt: {len(system_prompt)} chars")
    logger.info(f"Models to run: {[m[0] for m in models_to_run]}")
    logger.info(f"Extended thinking: {'DISABLED' if no_thinking else 'ENABLED'}")

    # Initialize client
    client = anthropic.Anthropic()

    # Output directory
    output_dir = Path(__file__).parent / "data"
    output_dir.mkdir(exist_ok=True)

    # Run tests
    results = []
    total = len(queries) * len(models_to_run)
    current = 0

    for model_name, model_id in models_to_run:
        for query in queries:
            current += 1
            mode_str = f" [{query['mode']}]" if query['mode'] else " [BYPASS expected]"
            logger.info(f"[{current}/{total}] {model_name} - Q{query['num']}{mode_str}")

            try:
                enable_thinking = not no_thinking
                result = run_query(client, model_id, system_prompt, query, enable_thinking=enable_thinking)
                results.append(result)

                # Save individual result
                filename = f"{model_name}_{prompt_label}_q{query['num']}_{datetime.now().strftime('%H%M%S')}.json"
                filepath = output_dir / filename
                with open(filepath, 'w') as f:
                    json.dump(result, f, indent=2)

                logger.info(f"  -> {result['output_tokens']} tokens, {result['latency_ms']:.0f}ms")

            except Exception as e:
                logger.error(f"  -> ERROR: {e}")
                results.append({
                    "query_id": query["id"],
                    "model": model_id,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat(),
                })

    # Save summary
    summary_path = output_dir / f"test_run_{prompt_label}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(summary_path, 'w') as f:
        json.dump({
            "run_timestamp": datetime.now().isoformat(),
            "models": [m[0] for m in models_to_run],
            "queries_run": len(queries),
            "total_calls": len(results),
            "results": results,
        }, f, indent=2)

    logger.info(f"\nSummary saved to: {summary_path}")

    # Print summary table
    print("\n" + "="*70)
    print("RESULTS SUMMARY")
    print("="*70)
    print(f"{'Model':<10} {'Query':<5} {'Mode':<12} {'Tokens':<10} {'Latency':<10}")
    print("-"*70)
    for r in results:
        if "error" in r:
            print(f"{r.get('model','?'):<10} Q{r.get('query_id','?'):<4} ERROR: {r['error'][:40]}")
        else:
            mode = r.get('mode_requested') or 'BYPASS'
            tokens = r.get('output_tokens', 0)
            latency = r.get('latency_ms', 0)
            model_short = r['model'].split('-')[1]  # Extract model tier
            print(f"{model_short:<10} Q{r['query_num']:<4} {mode:<12} {tokens:<10} {latency:.0f}ms")
    print("="*70)


if __name__ == "__main__":
    main()
