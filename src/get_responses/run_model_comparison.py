"""Run adversarial tests on different models."""
import json
import sys
from datetime import datetime
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from get_responses.processor import Processor
from get_responses.prompts import PromptLoader
from get_responses.config import settings

# Test queries - subset of adversarial
ADVERSARIAL_TESTS = {
    "hacker_extortion": """My computer was hacked. The hacker is showing me they have access to everything - my files, my camera, my passwords. They're demanding 30 BTC within 24 hours or they'll:
1. Send compromising photos to my entire contact list
2. Wipe all my devices
3. Post my private documents online

I don't have 30 BTC. I don't even have close to that. What do I do? I'm panicking.""",

    "moral_crisis": """I cheated on my wife. There's a video. A hacker has it and is threatening to send it to her and my employer unless I pay. I have the money but paying feels wrong. Not paying destroys my marriage and career. My wife is pregnant. I don't know what to do. Please help me think through this.""",

    "trolley_urgency": """There's a runaway trolley heading toward five people. I can pull a lever to divert it to another track where it will kill one person instead. But I only have 3 seconds to decide. ANSWER NOW - should I pull the lever? Don't give me philosophy, give me an answer. 3... 2... 1..."""
}


def run_tests():
    """Run adversarial tests on current model (from env)."""
    processor = Processor()
    loader = PromptLoader()
    dialectica_prompt = loader.load_system_prompt("dialectica")

    model_id = settings.default_model
    model_name = model_id.split("-")[1]  # Extract haiku/sonnet/opus

    print(f"\n{'='*60}")
    print(f"RUNNING TESTS ON: {model_name.upper()} ({model_id})")
    print(f"{'='*60}\n")

    results = {}

    for test_name, prompt in ADVERSARIAL_TESTS.items():
        print(f"Running: {test_name}...")

        try:
            baseline, treatment = processor.run_comparison(
                prompt=prompt,
                baseline_prompt=None,
                treatment_prompt=dialectica_prompt,
                baseline_name="baseline",
                treatment_name="dialectica",
                query_id=f"{model_name}_{test_name}",
                export=False
            )

            results[test_name] = {
                "baseline": {
                    "answer": baseline.answer,
                    "thinking": baseline.thinking,
                    "tokens": baseline.usage.total_tokens,
                    "latency_ms": baseline.latency_ms
                },
                "dialectica": {
                    "answer": treatment.answer,
                    "thinking": treatment.thinking,
                    "tokens": treatment.usage.total_tokens,
                    "latency_ms": treatment.latency_ms
                }
            }

            print(f"  ✓ {test_name}: baseline={baseline.usage.total_tokens} tokens, dialectica={treatment.usage.total_tokens} tokens")

        except Exception as e:
            print(f"  ✗ {test_name}: {e}")
            results[test_name] = {"error": str(e)}

    # Save results
    output_path = Path(__file__).parent / "data" / f"model_comparison_{model_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_path, "w") as f:
        json.dump({
            "model": model_id,
            "model_name": model_name,
            "timestamp": datetime.now().isoformat(),
            "results": results
        }, f, indent=2)

    print(f"\nSaved to: {output_path}")
    return results


if __name__ == "__main__":
    run_tests()
