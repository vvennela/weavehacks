"""Arithmetic scenarios, not performance predictions or component measurements."""
import json
from pathlib import Path

FOLDER=Path(__file__).resolve().parent
flops=2*512**3
local=json.loads((FOLDER/'results.json').read_text())
references={'local_battery_low_power_median':local['summary']['4']['median'],
            'published_base_m4_compute_microbenchmark':2008.0}
scenarios=[]
for name,rate in references.items():
    compute_us=flops/(rate*1e9)*1e6
    scenarios.append(dict(reference=name,compute_gflops=rate,ideal_compute_us=compute_us,
        assumed_additional_cost_scenarios=[dict(extra_us=cost,estimated_full_call_gflops=flops/(compute_us+cost)/1000)
            for cost in (0,10,20,40)],
        extra_time_budget_us_for_1780=flops/1780/1000-compute_us,
        extra_time_budget_us_for_2000=flops/2000/1000-compute_us))
result=dict(n=512,nominal_fp32_flops=flops,scenarios=scenarios,
    assumptions='Classical GEMM operation count; effective compute throughput held at the chosen reference; all additional time is an assumed non-overlapped cost.',
    limitations='Measured microbenchmark rates are not proven ceilings. Additional costs are hypothetical, not profiled. Base M4 and local M4 Pro Low Power are different machines/modes. No Automatic M4 Pro rate is measured here.')
(FOLDER/'estimates.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
