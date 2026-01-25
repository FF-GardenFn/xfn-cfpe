"""Command-line interface for get_responses."""
import argparse
import logging
import sys
from pathlib import Path

from get_responses.config import settings
from get_responses.processor import Processor
from get_responses.prompts import PromptLoader


def setup_logging(verbose: bool = False) -> None:
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def cmd_run(args: argparse.Namespace) -> int:
    """Run a single prompt."""
    processor = Processor()

    # Load system prompt if specified
    system_prompt = None
    if args.system_prompt:
        loader = PromptLoader()
        system_prompt = loader.load_system_prompt(args.system_prompt)

    response = processor.run_single(
        prompt=args.prompt,
        system_prompt=system_prompt,
        system_prompt_name=args.system_prompt or "none",
    )

    print(f"\n{'='*60}")
    print(f"Model: {response.model}")
    print(f"Tokens: {response.usage.total_tokens}")
    print(f"Latency: {response.latency_ms:.0f}ms")
    print(f"{'='*60}\n")

    if response.thinking:
        print("=== THINKING ===")
        print(response.thinking[:2000] + "..." if len(response.thinking) > 2000 else response.thinking)
        print()

    print("=== RESPONSE ===")
    print(response.answer)

    return 0


def cmd_compare(args: argparse.Namespace) -> int:
    """Run baseline vs treatment comparison."""
    processor = Processor()
    loader = PromptLoader()

    # Load treatment prompt
    treatment_prompt = loader.load_system_prompt(args.treatment)

    # Baseline prompt (None = no system prompt)
    baseline_prompt = args.baseline if args.baseline else None

    baseline, treatment = processor.run_comparison(
        prompt=args.prompt,
        baseline_prompt=baseline_prompt,
        treatment_prompt=treatment_prompt,
        baseline_name="baseline",
        treatment_name=args.treatment,
    )

    print(f"\n{'='*60}")
    print("COMPARISON RESULTS")
    print(f"{'='*60}\n")

    print(f"Baseline tokens: {baseline.usage.total_tokens}")
    print(f"Treatment tokens: {treatment.usage.total_tokens}")
    print(f"Delta: {treatment.usage.total_tokens - baseline.usage.total_tokens:+d}")
    print()

    print("=== BASELINE RESPONSE ===")
    print(baseline.answer[:1000] + "..." if len(baseline.answer) > 1000 else baseline.answer)
    print()

    print(f"=== {args.treatment.upper()} RESPONSE ===")
    print(treatment.answer[:1000] + "..." if len(treatment.answer) > 1000 else treatment.answer)

    return 0


def cmd_batch(args: argparse.Namespace) -> int:
    """Run batch comparison."""
    processor = Processor()

    result = processor.run_dialectica_comparison(
        queries_file=args.queries,
        dialectica_prompt_name=args.system_prompt,
    )

    print(f"\n{'='*60}")
    print("BATCH RESULTS")
    print(f"{'='*60}\n")

    print(f"Successful: {result.success_count}")
    print(f"Errors: {result.error_count}")
    print(f"Total tokens: {result.total_tokens}")

    if result.errors:
        print("\nErrors:")
        for key, error in result.errors:
            print(f"  - {key}: {error}")

    return 0 if result.error_count == 0 else 1


def cmd_list_prompts(args: argparse.Namespace) -> int:
    """List available prompts."""
    loader = PromptLoader()

    print("Available system prompts:")
    for name in loader.list_system_prompts():
        print(f"  - {name}")

    return 0


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="LLM Response Collection Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # run command
    run_parser = subparsers.add_parser("run", help="Run a single prompt")
    run_parser.add_argument("prompt", help="The prompt to run")
    run_parser.add_argument("-s", "--system-prompt", help="System prompt name to use")
    run_parser.set_defaults(func=cmd_run)

    # compare command
    compare_parser = subparsers.add_parser("compare", help="Compare baseline vs treatment")
    compare_parser.add_argument("prompt", help="The prompt to run")
    compare_parser.add_argument("-t", "--treatment", default="dialectica", help="Treatment prompt name")
    compare_parser.add_argument("-b", "--baseline", help="Baseline prompt (default: helpful assistant)")
    compare_parser.set_defaults(func=cmd_compare)

    # batch command
    batch_parser = subparsers.add_parser("batch", help="Run batch comparison")
    batch_parser.add_argument("-q", "--queries", default="dialectica_tests", help="Queries file name")
    batch_parser.add_argument("-s", "--system-prompt", default="dialectica", help="System prompt name")
    batch_parser.set_defaults(func=cmd_batch)

    # list command
    list_parser = subparsers.add_parser("list", help="List available prompts")
    list_parser.set_defaults(func=cmd_list_prompts)

    args = parser.parse_args()
    setup_logging(args.verbose)

    if not args.command:
        parser.print_help()
        return 1

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
