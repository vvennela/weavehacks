"""Compact the captured lab ledgers into one JSON the notebook can embed.

The notebook runs in the browser under Pyodide, where a network fetch is one more
thing that can fail in front of an audience. Embedding the data instead makes the
exported notebook self-contained: no fetch, no CORS, no auth interaction.

Run from the repository root:
    PYTHONPATH=src python scripts/build_lab_data.py
"""
import json
from pathlib import Path

from sera.spec import load_spec

ROOT = Path(__file__).resolve().parents[1]

# Display order is deliberate: ascending weight size, so the selector reads as a
# progression rather than an arbitrary list.
MODELS = [
    ("qwen3_8b", "Qwen3-8B", "Alibaba"),
    ("deepseek_r1_14b", "DeepSeek-R1-Distill-Qwen-14B", "DeepSeek"),
    ("moonlight_16b", "Moonlight-16B-A3B", "Moonshot AI (Kimi)"),
]


def compact(row: dict, baseline: dict | None) -> dict:
    """One ledger row reduced to what the notebook renders."""
    m = row.get("measurement") or {}
    cfg = row.get("config") or {}
    changed = {}
    if baseline:
        changed = {k: v for k, v in cfg.items() if baseline.get(k) != v and k != "model"}
    pred = row.get("prediction") or {}
    return {
        "trial_id": row["trial_id"],
        "round": row.get("round", 0),
        "verdict": row["verdict"],
        "specialist": row.get("proposing_specialist"),
        "lever": row.get("lever"),
        "changed": changed,
        "config": cfg,
        "p95_ms": m.get("p95_latency_ms"),
        "p50_ms": m.get("p50_latency_ms"),
        "throughput_rps": m.get("throughput_rps"),
        "footprint_gb": m.get("footprint_gb"),
        "quality_score": row.get("quality_score"),
        "quality_floor": row.get("quality_floor"),
        "reason": row.get("reason"),
        "rationale": pred.get("rationale"),
        "predicted_pct": pred.get("magnitude_pct"),
        "confidence": pred.get("confidence"),
        "prediction_held": row.get("prediction_held"),
        "substrate": row.get("substrate"),
    }


def main() -> int:
    out = {"models": []}
    for name, label, vendor in MODELS:
        ledger = ROOT / "runs" / "lab" / f"{name}.jsonl"
        spec_path = ROOT / "specs" / f"lab_{name}.yaml"
        if not ledger.exists():
            raise SystemExit(f"missing ledger {ledger} — run the spec first")
        rows = [json.loads(line) for line in ledger.read_text().splitlines() if line.strip()]
        spec = load_spec(str(spec_path))
        model, slo = spec.models[0], spec.slos[0]
        floor = spec.quality_floors[0]
        workload = spec.workloads[0]
        baseline_cfg = rows[0]["config"] if rows else None

        # Substrate is read off the rows rather than assumed, so that swapping in a
        # real vLLM ledger relabels the page automatically.
        substrates = sorted({r.get("substrate") for r in rows if r.get("substrate")})

        out["models"].append({
            "key": name,
            "label": label,
            "vendor": vendor,
            "hf_id": model.hf_id,
            "params_b": model.params_b,
            "num_layers": model.num_layers,
            "num_kv_heads": model.num_kv_heads,
            "head_dim": model.head_dim,
            "spec_file": f"specs/lab_{name}.yaml",
            "slo_p95_ms": slo.p95_latency_ms,
            "slo_min_throughput_rps": slo.min_throughput_rps,
            "quality_floor": floor.min_score,
            "workload": {
                "request_rate_rps": workload.request_rate_rps,
                "input_len_mean": workload.input_len_mean,
                "output_len_mean": workload.output_len_mean,
                "duration_s": workload.duration_s,
            },
            "gpu": spec.gpus[0].name,
            "vram_gb": spec.gpus[0].vram_gb,
            "substrate": substrates[0] if len(substrates) == 1 else "mixed",
            "trials": [compact(r, baseline_cfg) for r in rows],
        })

    target = ROOT / "notebooks" / "lab_runs.json"
    target.write_text(json.dumps(out, indent=1, allow_nan=False) + "\n")
    size = target.stat().st_size
    print(f"wrote {target.relative_to(ROOT)}  ({size:,} bytes)")
    for m in out["models"]:
        kept = [t for t in m["trials"] if t["verdict"] == "accepted"]
        print(f"  {m['label']:<34} {len(m['trials'])} trials, {len(kept)} accepted, substrate={m['substrate']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
