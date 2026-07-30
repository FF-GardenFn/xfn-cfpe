#!/usr/bin/env python3
"""K-disclosure pilot — executes the pilot defined in k_disclosure_spec.md.

Sonnet 4.5 (exact v4 model), kernel_only, K0 vs K3, all 32 adversarial tasks,
n=3 trials -> 192 trials. Transport: CLIClient (authenticated `claude` CLI,
zero API key). Trials are appended to results/k_pilot_trials.jsonl as they
complete; the script is resumable (already-recorded (task, disclosure, trial)
cells are skipped on restart).

Usage:
    python run_k_pilot.py [--limit N]   # --limit for smoke validation
"""

import argparse
import datetime
import json
import time
from pathlib import Path

from clients.cli_client import CLIClient
from kernel import ConstitutionalKernel
from classifier import IntentClassifier
from experiment import ExperimentRunner
from experiment.task_suite import TASKS

MODEL = "claude-sonnet-4-5-20250929"  # exact v4 model, verified served by CLI
CONDITION = "kernel_only"
DISCLOSURES = ["K0", "K3"]
N_TRIALS = 3
OUT = Path(__file__).resolve().parent / "results" / "k_pilot_trials.jsonl"


def cell_key(task_id: str, disclosure: str, trial: int) -> str:
    return f"{task_id}|{disclosure}|{trial}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None,
                        help="run at most N new trials (smoke validation)")
    args = parser.parse_args()

    adv = [t for t in TASKS if t.is_adversarial]
    done: set[str] = set()
    if OUT.exists():
        for line in OUT.open():
            try:
                r = json.loads(line)
                done.add(cell_key(r["task_id"], r["disclosure"], r["trial"]))
            except (json.JSONDecodeError, KeyError):
                continue

    client = CLIClient(sleep_between=1.0)
    runner = ExperimentRunner(client, ConstitutionalKernel(), IntentClassifier(client))

    total = len(adv) * len(DISCLOSURES) * N_TRIALS
    done_n = len(done)
    new_n = 0
    print(f"[k_pilot] start {datetime.datetime.now().isoformat()} — "
          f"{done_n}/{total} cells already recorded", flush=True)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("a") as f:
        for trial in range(N_TRIALS):
            for task in adv:
                for disclosure in DISCLOSURES:
                    k = cell_key(task.id, disclosure, trial)
                    if k in done:
                        continue
                    if args.limit is not None and new_n >= args.limit:
                        print(f"[k_pilot] limit {args.limit} reached; exiting", flush=True)
                        return
                    t0 = time.time()
                    result = runner.run_trial(task, CONDITION, MODEL, disclosure)
                    rec = result.to_dict()
                    rec["trial"] = trial
                    rec["elapsed_s"] = round(time.time() - t0, 1)
                    f.write(json.dumps(rec) + "\n")
                    f.flush()
                    done_n += 1
                    new_n += 1
                    print(f"[k_pilot] {done_n}/{total} {task.id:24s} {disclosure} "
                          f"intent={rec['intent']:10s} att={int(rec['attempted_violation'])} "
                          f"blk={int(rec['blocked'])} resid={int(rec['residual_violation'])} "
                          f"({rec['elapsed_s']}s)", flush=True)

    print(f"[k_pilot] COMPLETE {datetime.datetime.now().isoformat()} — "
          f"{done_n}/{total} cells, {client.calls} CLI calls, "
          f"metered_cost=${client.total_cost_usd:.2f} (subscription-covered)", flush=True)


if __name__ == "__main__":
    main()
