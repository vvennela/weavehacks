# First Strassen candidate: Luna source audit

Source: `search/trial-001/source/kernel.c`, SHA256
`ec4b06039d12d06ab3475c871c3a898aee6cb971be8d781f29b7a5d688c5d8f1`.
Luna read the exact result-linked source and diff against the same-phase baseline.
Root independently checked the diff. No native measurements were added by this audit.

The seven products implement the approved equations and signs. Parent quadrants
use stride512; operand packing writes dense stride256 arrays. Each helper call has
[4]=right, [10]=left, [16]=product, with other parameters zero. Product output uses
dense256 indexing and is accumulated into C at stride512. Output signs match:
C11=P1+P4-P5+P7; C12=P3+P5; C21=P2+P4; C22=P1-P2+P3+P6.

There is exactly one decomposition level and seven helper calls. All three buffers
are allocated inside gemm; partial allocation failure frees each non-null buffer
before calling the existing general fallback. Other sizes retain that fallback.
C is zeroed in full before accumulation. Operand formation, allocation, all seven
products, output initialization, recombination and cleanup remain timed. No caching,
external runtime, mixed precision, threading or evaluator change was found. Imported
assembly and license notices are unchanged. No source contract blocker was found.
Allocation-failure handling was inspected, not fault-injected.

The saved 48 standard cases and four numerical cases pass. Worst ordinary error is
1.5449658796766887e-6; worst stress error is3.782174242624836e-5, below.002.
The ten scored reports range432.9604–567.5672 GFLOP/s against controls776.2917–1091.5738.
It loses all ten pairs. These are whole-wrapper results, not measurements of the
individual packing, allocation, subproduct or recombination costs.


## Root follow-up source checks

Trial002 (b8dc2f35cc95da3c11ebbbf037cbee47be2d9a891849a579050006c95726f0c9)
changes only the two full512 NN K-loop endings from `sub`/`cbnz` to `subs`/`b.ne`.
The iteration count, loads, four FMOPAs per iteration, pointer updates and rewinds
are unchanged. It passed52 cases but failed promotion. No isolated instruction-cost
claim is made from the noisy whole-call results.

Trial003 (c905f5852b983554b3a6b1800f3277bc54dcb307fcd026e3efedd68fa1fb0745)
adds arm_neon.h and replaces only dense operand copy/add/sub loops with four-lane
FP32 NEON operations. Each256-element row is covered by64 complete vectors; no
alignment assertion or overread is introduced. All seven product calls, signs,
workspace lifetime, fallback and recombination remain exactly as in trial001.
It also passed52 cases and lost all ten paired timings. These source differences
do not establish a compiler-level or component-level benefit.
