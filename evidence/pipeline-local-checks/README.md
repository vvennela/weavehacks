# Packaged pipeline: local validation

This is manual synthetic control-flow validation, not GPU or model-quality evidence.

The real `optimize` and measurement code ran with a substituted runner. Each case used an isolated temporary output directory. The check read `result.json` after close and verified that no fixture runner remained live.

| Fixture | Observed outcome |
| --- | --- |
| Identical tokens; candidate p95 90 ms versus baseline 100 ms | Candidate selected and returned live |
| Empty candidate output | Candidate rejected; baseline reloaded and returned live |
| Candidate startup raises an error | Baseline reloaded and returned live |
| Cleanup raises an error | Run failed; no runner returned; failure record saved |

Separate manual gate checks passed at the exact 5% boundary and rejected empty outputs and an empty reference.

The automated suite passed 65 tests, covering candidate validation, memory arithmetic, saved metrics parsing, and the previously approved benchmark graders. `compileall` passed for the Sera package. These local checks do not complete the live milestone.

## User-priority checkpoint

The updated suite passes 97 tests. Additional candidate-validation checks cover invalid objectives, quality rejection under throughput optimization, missing memory measurements, configurable improvement thresholds, and retaining nondominated trade-offs.

A manual synthetic pipeline check supplied identical quality outputs, baseline p95 100 ms and throughput 100 tokens/s, and candidate p95 110 ms and throughput 120 tokens/s. Latency priority returned the baseline; throughput priority returned the candidate. Both retained both trials on the frontier. The check verified objective delivery to proposal and feedback, the selected runner configuration, the saved report, and cleanup. Provider validation and GPU execution were replaced by explicitly labeled fixtures. This is wiring evidence, not real performance or agent-reasoning evidence.

## Verified task gate checkpoint

The suite now passes 120 tests, including evaluator failure, malformed score, missing output, hard latency/memory limits, and invalid verified-mode input. Manual synthetic pipeline checks verified three outcomes: different correct answers passed and selected the faster candidate; two wrong configurations returned no runner; and a slower correct candidate replaced a wrong baseline with outcome `feasible`. All fixture runtimes closed. No GPU or provider call was used in these checks.

An offline audit applied the existing strict JSON task grader to the saved eight-prompt quality outputs from mvp-agent-v1. Both configurations scored 0/8 format-valid responses because every response included fences, prose, code, or incomplete JSON. This post-run diagnostic does not replace the original token-agreement decision or establish zero semantic accuracy. A future strict-task run must name its prompt and evaluator contract before execution.
