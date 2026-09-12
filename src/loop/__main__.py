"""Run the loop.

    python -m loop --spec specs/demo.yaml

Phase 1 tunes each model alone, Phase 2 asks whether they can share a card. Both
write to one ledger, and Phase 2 reads what Phase 1 wrote.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from . import tracing
from .ledger import Ledger
from .phase1 import Phase1
from .phase2 import Phase2
from .runner.base import TrialRunner
from .runner.sim_runner import SimRunner
from .spec import load_spec


def select_runner(force_sim: bool = False) -> TrialRunner:
    """Real hardware when it is reachable, the analytic model otherwise.

    The choice is announced rather than silent: a run that quietly fell back to
    simulation and reported the numbers as measurements would be worse than useless.
    """
    if force_sim or not os.environ.get("LOOP_VLLM_HOST"):
        return SimRunner()

    try:
        from .runner.vllm_runner import VllmRunner  # noqa: PLC0415

        runner = VllmRunner()
        if runner.available():
            return runner
        print("  [runner] vLLM host configured but unreachable — using simulator")
    except ImportError as exc:
        print(f"  [runner] vLLM runner unavailable ({exc}) — using simulator")
    return SimRunner()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="loop", description=__doc__)
    ap.add_argument("--spec", default="specs/demo.yaml")
    ap.add_argument("--ledger", default="runs/ledger.jsonl")
    ap.add_argument("--sim", action="store_true", help="force the simulator")
    ap.add_argument("--phase", choices=["1", "2", "both"], default="both")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--fresh", action="store_true", help="discard any existing ledger")
    args = ap.parse_args(argv)

    spec = load_spec(args.spec)
    ledger_path = Path(args.ledger)
    if args.fresh and ledger_path.exists():
        ledger_path.unlink()

    traced = tracing.init()
    runner = select_runner(force_sim=args.sim)
    ledger = Ledger(ledger_path)
    verbose = not args.quiet

    if verbose:
        print(f"  spec       {args.spec}  ({len(spec.models)} models, {len(spec.gpus)} GPUs)")
        print(f"  substrate  {runner.substrate.value}")
        print(f"  tracing    {'weave' if traced else 'off'}")
        print(f"  ledger     {ledger_path}")

    if args.phase in ("1", "both"):
        Phase1(spec, runner, ledger, verbose=verbose).run()

    if args.phase in ("2", "both"):
        result = Phase2(spec, runner, ledger, verbose=verbose).run()
        if verbose:
            print(f"\n{'=' * 74}\n  SUMMARY\n{'=' * 74}")
            print(json.dumps(ledger.summary(), indent=2))
            if result.consolidated:
                print(f"\n  Consolidated onto one GPU. {result.gpu_freed} freed.")
            else:
                print(f"\n  Not consolidated: {result.reason}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
