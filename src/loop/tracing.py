"""Weave tracing that degrades to nothing when Weave is absent.

The loop must run on a laptop with no W&B account and produce identical results. So
`op` is a decorator that wraps with weave.op when tracing is live and returns the
function untouched otherwise — no import error, no config branch at every call site,
no behavioural difference.

What the trace is for: judges asking "why did it propose that, and what happened" get
a tree — proposal, arbitration, trial, gate — instead of a wall of stdout.
"""

from __future__ import annotations

import functools
import os
from typing import Any, Callable, TypeVar

F = TypeVar("F", bound=Callable[..., Any])

_ENABLED = False
_WEAVE: Any = None


def init(project: str | None = None, enabled: bool | None = None) -> bool:
    """Start Weave if it is installed and a key is present. Returns whether it is live."""
    global _ENABLED, _WEAVE

    if enabled is False:
        _ENABLED = False
        return False

    if not os.environ.get("WANDB_API_KEY"):
        return False

    try:
        import weave  # noqa: PLC0415
    except ImportError:
        return False

    project = project or os.environ.get("WANDB_PROJECT", "weavehacks")
    entity = os.environ.get("WANDB_ENTITY")
    target = f"{entity}/{project}" if entity else project

    try:
        weave.init(target)
    except Exception as exc:  # noqa: BLE001 - tracing must never break a run
        print(f"  [trace] weave.init failed, continuing untraced: {exc}")
        return False

    _WEAVE = weave
    _ENABLED = True
    return True


def enabled() -> bool:
    return _ENABLED


def op(fn: F) -> F:
    """Mark a function as a traced operation.

    Applied at import time, before init() has run, so it defers the decision to call
    time rather than capturing the flag's value at decoration.
    """

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        if _ENABLED and _WEAVE is not None:
            traced = getattr(fn, "_weave_traced", None)
            if traced is None:
                traced = _WEAVE.op(fn)
                fn._weave_traced = traced  # type: ignore[attr-defined]
            return traced(*args, **kwargs)
        return fn(*args, **kwargs)

    return wrapper  # type: ignore[return-value]
