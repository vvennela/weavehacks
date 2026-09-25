# One-level Strassen and classical-method swarm

Status: prepared; no performance result yet.

The user approved one-level FP32 Strassen alongside current methods. Astra-high can
select the new `strassen_one_level` role among exactly 15 Luna specialists. They
propose and rank experiments together; Astra implements their queue and reviews
measured outcomes. No kernel experiment or order is selected by the root agent.
Only Codex agents through ChatGPT login are used.

The prepared baseline retains the active full512 NN kernel and existing unused
helpers, and adds the exact pinned, unused LIBXSMM256 primitive. Source SHA256:
`8bb0113e377808a841819354296fa0ef02ff49e4188d57a091afc6463fc0ca18`.
All five compiled NN/TA/TB/TT/n256 bodies match the exported bytes. Baseline passed
48 existing correctness cases and four deterministic cancellation/scale cases.
Adding unused code changes binary layout, so fresh baseline measurements are required.
No preparation result is a speedup claim.

The new numerical checks use two cancellation cases (opposite 256-square blocks
with seeded FP32 perturbations of .03125 and .0625) and two scale cases (signed
powers of two with exponent ranges ±8 and ±12 and small mantissa perturbations).
They retain the .002 max-absolute-error/max-reference check using float64 reference
from actual FP32 inputs, finite outputs, untouched inputs, output guards and nonzero
initial C. These are correctness-only checks before timing; the official hill is
unchanged. They do not prove accuracy on all inputs.

Caps and rules are unchanged: six implementation attempts, 108 calls, 180 seconds
per agent call, 1800 seconds total, ten validations and ten alternating paired
controls per candidate, min(candidate)>1.05*max(control), then held-out confirmation.
Source and power settings remain fixed during the block. AC and battery evidence
are separate. All packing, sums, workspace, products and recombination are timed.
No deeper recursion, Winograd schedule, mixed precision or external runtime.

Goal comparisons include both the historical imported peaks and fresh same-mode
controls; the legacy1800 target flag is not the new goal definition. Historical-vs-
fresh comparator remains awaiting user adjudication. No imported primitive or
unchanged baseline can be counted as a Sera improvement.

Preparation and driver tests: 9 passed. Relevant prompt/advisory/search/edit/ranking
tests: 64 passed. `prepare.py` checks exact imported source and compiled bytes;
`numerics.py` contains the extra correctness cases; `run.py` runs the frozen search.
