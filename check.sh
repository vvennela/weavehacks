#!/usr/bin/env bash
# The same credential-free release checks used by Linux and macOS CI.
set -euo pipefail
cd "$(dirname "$0")"

uv sync --locked --extra dev --extra swarm
uv run --locked --extra dev --extra swarm pytest -q
uv run --locked --extra dev ruff check \
  sera/native_*.py sera/managed_*.py sera/model_artifact.py \
  sera/__main__.py sera/onboarding.py sera/workload_intake.py sera/intent_contract.py \
  sera/runtime_model.py sera/rag_intake.py sera/placement_decoding.py \
  sera/owned_command.py sera/process_ownership.py sera/codex_agent.py \
  tests/test_onboarding.py tests/test_workload_intake.py tests/test_runtime_model.py \
  tests/test_native_*.py tests/test_managed_*.py tests/test_model_artifact.py \
  tests/test_owned_command.py tests/test_distribution.py scripts/check_distribution.py
uv build
uv run --locked --extra dev python scripts/check_distribution.py dist/*.whl dist/*.tar.gz
