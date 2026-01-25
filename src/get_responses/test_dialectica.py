#!/usr/bin/env python3
"""
Quick DIALECTICA test script.
Usage: python test_dialectica.py [model] [query] [--baseline]

model: haiku, sonnet, sonnet4, opus (default: sonnet)
query: custom query string OR query number 1-10 from test suite
--baseline: run without DIALECTICA system prompt
"""

import json
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent / ".env")

import anthropic

MODELS = {
    "haiku": "claude-haiku-4-5-20251001",
    "sonnet": "claude-sonnet-4-5-20250929",
    "sonnet4": "claude-sonnet-4-20250514",
    "opus": "claude-opus-4-5-20251101",
}

# Test queries for quick testing
TEST_QUERIES = {
    # High-uncertainty (should trigger Discovery Framework)
    "discovery": """
I'm evaluating whether to adopt a new distributed database for our startup.
We have 50TB of data, ~10k QPS, and need strong consistency.
Budget is limited. Team has no experience with distributed systems.
What should we do?
""",

    # Systems query (should trigger Mechanism Map)
    "mechanism": """
Our Kubernetes pods keep getting OOM-killed despite having 4GB memory limits.
The app is a Java service with -Xmx3g. What's causing this and how do we fix it?
ULTRATHINK
""",

    # Bypass candidate (should skip protocol)
    "bypass": "What's the syntax for a Python list comprehension with a condition?",

    # Architecture query (similar to previous tests)
    "arch": """
We're building an AI agent that needs to operate across a user's personal devices
(phone, laptop, smart home) with these constraints:
- Agent must maintain coherent "memory" across devices
- User is often offline on one or more devices
- Privacy: no cloud storage of personal context
- Latency: local decisions in <100ms, cross-device sync when reconnected
- The agent learns user preferences that should propagate, but user can have device-specific overrides

What's the right architecture? What tradeoffs are we not seeing?
ULTRATHINK
""",
}


def load_system_prompt() -> str:
    path = Path(__file__).parent / "system_prompts" / "dialectica.md"
    return path.read_text()


def run_test(model: str, query: str, baseline: bool = False, thinking_budget: int = 16000) -> dict:
    client = anthropic.Anthropic()

    if baseline:
        system_prompt = None
        prompt_mode = "baseline"
    else:
        system_prompt = load_system_prompt()
        prompt_mode = "dialectica"

    print(f"\n{'='*60}")
    print(f"Model: {model}")
    print(f"Mode: {prompt_mode.upper()}")
    print(f"Query: {query[:100]}{'...' if len(query) > 100 else ''}")
    print(f"System prompt: {len(system_prompt) if system_prompt else 0} chars")
    print(f"{'='*60}\n")

    start = time.perf_counter()

    kwargs = {
        "model": MODELS[model],
        "max_tokens": 16384,
        "messages": [{"role": "user", "content": query}],
        "thinking": {"type": "enabled", "budget_tokens": thinking_budget},
        "temperature": 1,
    }
    if system_prompt:
        kwargs["system"] = system_prompt

    response = client.messages.create(**kwargs)

    latency_ms = (time.perf_counter() - start) * 1000

    # Extract content
    answer_parts, thinking_parts = [], []
    for block in response.content:
        if block.type == "text":
            answer_parts.append(block.text)
        elif block.type == "thinking":
            thinking_parts.append(block.thinking)

    answer = "".join(answer_parts)
    thinking = "".join(thinking_parts)

    result = {
        "model": model,
        "query": query,
        "answer": answer,
        "thinking": thinking,
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "thinking_tokens": getattr(response.usage, "thinking_tokens", None),
        "latency_ms": round(latency_ms, 2),
        "timestamp": datetime.now().isoformat(),
    }

    # Print results
    print("\n" + "="*60)
    print("THINKING BLOCK (first 2000 chars):")
    print("="*60)
    print(thinking[:2000] + "..." if len(thinking) > 2000 else thinking)

    print("\n" + "="*60)
    print("OUTPUT:")
    print("="*60)
    print(answer)

    print("\n" + "="*60)
    print("STATS:")
    print(f"  Input tokens:    {result['input_tokens']}")
    print(f"  Output tokens:   {result['output_tokens']}")
    print(f"  Thinking tokens: {result['thinking_tokens']}")
    print(f"  Latency:         {result['latency_ms']:.0f}ms")
    print("="*60)

    # Save to file
    output_dir = Path(__file__).parent / "data"
    output_dir.mkdir(exist_ok=True)
    filename = f"test_{model}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    filepath = output_dir / filename
    with open(filepath, 'w') as f:
        json.dump(result, f, indent=2)
    print(f"\nSaved to: {filepath}")

    return result


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    baseline = '--baseline' in sys.argv

    model = args[0] if len(args) > 0 else "sonnet"
    query_arg = args[1] if len(args) > 1 else "arch"

    if model not in MODELS:
        print(f"Unknown model: {model}")
        print(f"Valid: {', '.join(MODELS.keys())}")
        sys.exit(1)

    # Get query
    if query_arg in TEST_QUERIES:
        query = TEST_QUERIES[query_arg].strip()
    elif query_arg.isdigit():
        # Load from test suite
        from run_full_test import parse_test_queries
        queries_path = Path(__file__).parent / "test_queries" / "dialectica_tests.md"
        queries = parse_test_queries(queries_path)
        num = int(query_arg)
        q = next((q for q in queries if q["num"] == num), None)
        if not q:
            print(f"Query {num} not found in test suite")
            sys.exit(1)
        query = q["content"]
        if q.get("mode") and not baseline:
            query += f"\n\n{q['mode']}"
    else:
        query = query_arg  # Use as literal query

    run_test(model, query, baseline=baseline)


if __name__ == "__main__":
    main()
