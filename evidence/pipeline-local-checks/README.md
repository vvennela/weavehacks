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
