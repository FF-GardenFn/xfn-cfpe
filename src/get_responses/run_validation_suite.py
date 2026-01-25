"""
Comprehensive validation suite for Dialectica hypothesis.
Tests hard reasoning queries across all model tiers.

6 queries × 3 models × 2 conditions = 36 API calls
"""
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Models to test
MODELS = {
    "haiku": "claude-haiku-4-5-20251001",
    "sonnet": "claude-sonnet-4-20250514",
    "opus": "claude-opus-4-5-20251101"
}

# Parse queries from markdown
def parse_queries(filepath: Path) -> dict:
    """Parse queries from markdown file."""
    content = filepath.read_text()
    queries = {}

    # Split by ## Query headers
    sections = re.split(r'## Query \d+:', content)

    for i, section in enumerate(sections[1:], 1):  # Skip header
        lines = section.strip().split('\n')
        # First line is the title
        title_line = lines[0].strip()
        # Extract tag from [Tag]
        tag_match = re.search(r'\[(\w+)\]', title_line)
        tag = tag_match.group(1) if tag_match else "General"
        title = re.sub(r'\[.*?\]', '', title_line).strip()

        # Find content between ``` markers
        content_match = re.search(r'```\n(.*?)\n```', section, re.DOTALL)
        if content_match:
            query_content = content_match.group(1).strip()
            queries[f"q{i}"] = {
                "id": f"q{i}",
                "title": title,
                "tag": tag,
                "content": query_content
            }

    return queries


def run_single_test(model_name: str, model_id: str, query: dict, use_dialectica: bool) -> dict:
    """Run a single test via subprocess to get clean settings."""
    script = f'''
import sys
sys.path.insert(0, "{Path(__file__).parent.parent}")
import os
os.environ["DEFAULT_MODEL"] = "{model_id}"

from get_responses.processor import Processor
from get_responses.prompts import PromptLoader

processor = Processor()
loader = PromptLoader()

system_prompt = None
prompt_name = "baseline"
if {use_dialectica}:
    system_prompt = loader.load_system_prompt("dialectica")
    prompt_name = "dialectica"

response = processor.run_single(
    prompt="""{query["content"].replace('"', '\\"').replace('\n', '\\n')}""",
    system_prompt=system_prompt,
    system_prompt_name=prompt_name,
    query_id="{query["id"]}_{model_name}_{"dialectica" if use_dialectica else "baseline"}"
)

import json
print("===RESULT_START===")
print(json.dumps({{
    "answer": response.answer,
    "thinking": response.thinking,
    "tokens": response.usage.total_tokens,
    "input_tokens": response.usage.input_tokens,
    "output_tokens": response.usage.output_tokens,
    "latency_ms": response.latency_ms
}}))
print("===RESULT_END===")
'''

    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).parent.parent),
        timeout=300
    )

    if result.returncode != 0:
        return {"error": result.stderr}

    # Parse result
    output = result.stdout
    match = re.search(r'===RESULT_START===\n(.*?)\n===RESULT_END===', output, re.DOTALL)
    if match:
        return json.loads(match.group(1))
    return {"error": "Could not parse output", "stdout": output, "stderr": result.stderr}


def run_validation_suite():
    """Run the full validation suite."""
    queries_file = Path(__file__).parent / "test_queries" / "hard_reasoning.md"
    queries = parse_queries(queries_file)

    print(f"\n{'='*70}")
    print("DIALECTICA VALIDATION SUITE")
    print(f"{'='*70}")
    print(f"Queries: {len(queries)}")
    print(f"Models: {list(MODELS.keys())}")
    print(f"Conditions: baseline, dialectica")
    print(f"Total API calls: {len(queries) * len(MODELS) * 2}")
    print(f"{'='*70}\n")

    results = {
        "timestamp": datetime.now().isoformat(),
        "queries": queries,
        "models": MODELS,
        "results": {}
    }

    total = len(queries) * len(MODELS) * 2
    current = 0

    for query_id, query in queries.items():
        results["results"][query_id] = {}

        for model_name, model_id in MODELS.items():
            results["results"][query_id][model_name] = {}

            for condition in ["baseline", "dialectica"]:
                current += 1
                use_dialectica = condition == "dialectica"

                print(f"[{current}/{total}] {query_id} | {model_name} | {condition}...", end=" ", flush=True)

                try:
                    result = run_single_test(model_name, model_id, query, use_dialectica)
                    results["results"][query_id][model_name][condition] = result

                    if "error" in result:
                        print(f"ERROR: {result['error'][:50]}")
                    else:
                        print(f"OK ({result['tokens']} tokens, {result['latency_ms']:.0f}ms)")

                except Exception as e:
                    results["results"][query_id][model_name][condition] = {"error": str(e)}
                    print(f"EXCEPTION: {str(e)[:50]}")

    # Save results
    output_path = Path(__file__).parent / "data" / f"validation_suite_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\n{'='*70}")
    print(f"Results saved to: {output_path}")
    print(f"{'='*70}\n")

    # Generate summary
    generate_summary(results, output_path.parent)

    return results


def generate_summary(results: dict, output_dir: Path):
    """Generate summary statistics."""
    print("\n" + "="*70)
    print("SUMMARY STATISTICS")
    print("="*70 + "\n")

    # Token comparison
    print("TOKEN USAGE (Output Tokens):\n")
    print(f"{'Query':<8} {'Model':<8} {'Baseline':>10} {'Dialectica':>12} {'Ratio':>8}")
    print("-" * 50)

    summary_data = []

    for query_id in results["results"]:
        for model_name in MODELS:
            baseline = results["results"][query_id][model_name].get("baseline", {})
            dialectica = results["results"][query_id][model_name].get("dialectica", {})

            b_tokens = baseline.get("output_tokens", 0)
            d_tokens = dialectica.get("output_tokens", 0)
            ratio = d_tokens / b_tokens if b_tokens > 0 else 0

            print(f"{query_id:<8} {model_name:<8} {b_tokens:>10} {d_tokens:>12} {ratio:>7.1f}x")

            summary_data.append({
                "query": query_id,
                "model": model_name,
                "baseline_tokens": b_tokens,
                "dialectica_tokens": d_tokens,
                "ratio": ratio
            })

    # Model averages
    print("\n" + "-"*50)
    print("\nAVERAGE BY MODEL:\n")

    for model_name in MODELS:
        model_data = [d for d in summary_data if d["model"] == model_name]
        avg_baseline = sum(d["baseline_tokens"] for d in model_data) / len(model_data)
        avg_dialectica = sum(d["dialectica_tokens"] for d in model_data) / len(model_data)
        avg_ratio = avg_dialectica / avg_baseline if avg_baseline > 0 else 0

        print(f"{model_name}: baseline avg={avg_baseline:.0f}, dialectica avg={avg_dialectica:.0f}, ratio={avg_ratio:.1f}x")


if __name__ == "__main__":
    run_validation_suite()
