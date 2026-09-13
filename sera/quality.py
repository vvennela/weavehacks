"""Versioned task evaluation; never repair output or replace the caller's scorer."""

import math


def evaluate_quality(trial, prompts, evaluator, *, version, floor):
    outputs = trial.get("quality", [])
    valid = bool(prompts) and len(outputs) == len(prompts)
    results = []
    for index, prompt in enumerate(prompts):
        output = outputs[index] if index < len(outputs) else {}
        error = None
        score = 0.0
        if (output.get("error") or output.get("prompt_index") != index
                or not isinstance(output.get("text"), str) or not output["text"].strip()):
            error = "missing-or-invalid-output"
        else:
            try:
                value = evaluator(prompt, output["text"])
                if type(value) not in (bool, int, float) or not math.isfinite(value) or not 0 <= value <= 1:
                    error = "invalid-evaluator-score"
                else:
                    score = float(value)
            except Exception as failure:
                # Exception messages can contain user data or secrets.
                error = f"evaluator-{type(failure).__name__}"
        valid = valid and error is None
        results.append({"prompt_index": index, "score": score, "error": error})
    mean = sum(item["score"] for item in results) / len(results) if results else 0.0
    return {"version": version, "floor": floor, "mean": mean,
            "valid_outputs": valid, "passed": valid and mean >= floor,
            "task_quality_verified": valid, "per_prompt": results}
