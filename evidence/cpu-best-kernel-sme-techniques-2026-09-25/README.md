# SME techniques applied to the best Sera kernel

Status: prepared.

The user requested implementation of techniques behind the published~2,000GFLOP/s
SME peak. This phase stays on the exact best panel32 source `eb091b1e…`, replaying it
first against its original imported `04fc3ff…` control. Then15Luna specialists jointly
rank distinct changes to that active panel body; Astra-high implements and reviews.
The inactive full512 assembly, Strassen and unrelated algorithms are outside this
phase's scope. No proposal or implementation has been chosen by root.

The board receives primary-source technique mapping, all prior outcomes, and a separate
local compute-only calibration. Four-tile independence, load reuse and one SME region
are already present. New advice must change actual scheduling/layout/alignment rather
than rename these existing features. The calibration is not GEMM or a promotion score.

Keep the current power/settings throughout the block, ten fresh baseline reports and
ten alternating validation/control pairs for each candidate,48public correctness cases,
frozenhill/tolerance.002/compiler/thread rules, min(candidate)>1.05*max(control), and
held-out confirmation. All packing, memory operations, transitions and allocation are
timed. The6candidate-slot,108call,180second/call and1800second/block caps are unchanged;
one candidate slot replays the saved best source. Raw timing triplets stay in reports.

Four preflight/source/replay tests pass, as do43advisory/search tests. No previous timing
enters eligibility. The new implementation needs measured correctness and a repeatable
improvement; a copied microbenchmark peak or theoretical estimate cannot meet the goal.
