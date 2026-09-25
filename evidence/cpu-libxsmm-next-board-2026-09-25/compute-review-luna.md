# Remaining source-grounded hypotheses for the next board

This is a read-only review of `cpu-libxsmm-generator-2026-09-25/baseline/kernel.c`, the prior `layout-review-luna.md`, and the completed panel-swarm and Automatic replay records. It proposes candidate questions only. It does not rank or select them. No observed result identifies a compute, memory, or streaming bottleneck.

## Evidence already tested

The original full-size kernel remains the incumbent. In both `Llibxsmm_478` and `Llibxsmm_70c`, each K iteration loads two vector pairs, advances the pointers, executes four FP32 FMOPA instructions into ZA0–ZA3, decrements the counter, and branches. The kernel packs its operand into 128 KiB of stack scratch, then runs two 512-K loops for its output halves.

The completed `next-continue` block already tested three nearby K-loop schedules: counter decrement before FMOPA, pointer updates after FMOPA, and pointer updates interleaved with FMOPA. None promoted. Do not reissue these as separate proposals. The panel-swarm tested sixteen 32-row helper calls, a C SME fallback with constant 512 bounds, and 272-byte padded A slices. All passed correctness but none promoted. Automatic replay used the exact same sources and also promoted none; its higher, highly variable scores do not prove a source improvement or a power-mode effect. The detailed reports do not provide stage timings or hardware counters.

## Distinct implementation questions for specialists

### Two-K pipeline: already tested; only loop-control simplification is distinct

Root checked the actual `ec83ff3b…` source diff in `cpu-libxsmm-measure-prepared-2026-09-24`: both loops already load K0 into z0–z3 and K1 into z4–z7, issue the eight FMOPAs in contribution order, and advance two strides. The earlier claim that this second bank was untested was incorrect. Do not propose that pipeline again as a new mechanism.

The tested source retains a compare/branch and an unreachable odd-K tail for the fixed K=512 shape. A separate, narrow hypothesis is to use a 256-iteration loop over the existing two-K body and remove that unnecessary tail/control logic. This reduces loop-control instructions only; the two-bank load schedule is already measured. Whether that smaller change matters is unknown. Specialists may rank or reject it without attributing old pipeline behavior to a new experiment.

### Operand orientation using a generator-supported transpose descriptor (preparation required)

**Source fact:** The pinned LIBXSMM SME generator supports transpose descriptor flags, but the legal mapping requires the physical input layout and leading dimensions to agree with the flags. The current row-major ABI is implemented through the column-major identity `Cᵀ = Bᵀ Aᵀ`. The generator review documents legal descriptor and panel choices; a flag-only flip on the current pointers would compute the wrong operation. Prior C SME and panel-helper candidates do not test this descriptor/layout pairing in the original one-call 512×512 generated kernel.

**Candidate:** Export one full 512×512 beta-zero SME primitive with a changed transpose flag and explicitly matched operand buffer/pointer mapping. Write the exact logical element equations and leading dimensions before changing the wrapper. Any transpose or pack needed to create the matching storage must happen inside `gemm` and remain timed; preserve output overwrite semantics and the unchanged non-512 fallback. Do not assume a flag avoids the current pack: inspect the emitted code and confirm which transpose/pack path is actually removed or added before proposing the measurement.

**Hypothesis, not a result:** A different operand orientation may change or remove packing and improve access. Explicit conversion may simply move the cost, and the generator source only establishes legality—not a benefit for the exact full-size call. This is not directly executable by the current Astra implementation agent: exporting and validating a new primitive requires host-side LIBXSMM generator access. Treat it as a preparation task for a later board, not as a current 180-second implementation candidate.

### Keep packed scratch reserved through its consumers (lifetime invariant)

**Source fact:** At `Llibxsmm_64`, `x20` saves the incoming stack pointer, the code reserves 128 KiB, and `x3`/`x26` hold the scratch base. `Llibxsmm_78` writes the packed data through `[sp]` while advancing `sp` upward by 0x100-byte stores until it returns to the saved top. The current `mov sp,x20` then restores the stack pointer before `Llibxsmm_478` and `Llibxsmm_70c` consume the still-addressable region through `x3`. Apple documents a 128-byte ARM64 stack red zone below SP; the packed 128 KiB region is larger and is outside that guarantee ([Apple ARM64 ABI guidance](https://developer.apple.com/documentation/xcode/writing-arm64-code-for-apple-platforms)). The assembly makes no intervening C calls or explicit stack stores, so the available evidence does not show a correctness failure; it does show that most of the scratch storage is no longer represented as live stack allocation during its reads.

**Candidate invariant repair:** Keep SP at the allocated scratch base throughout both packing and compute. Use a dedicated available integer register as the packing-store cursor instead of incrementing SP; preserve the cursor's ABI obligations. Keep x26 as the original scratch base and x3 as the compute cursor. Restore SP from x20 only after both consumers, before the outer loop's next allocation. Merely resetting SP after packing protects compute but leaves the packing-stage lifetime gap. Validate exact control-flow placement and all eight packing stores/increments before evaluation.

**Classification:** This is a stack-lifetime/ABI audit question, not a performance hypothesis. No failure or speed impact has been measured. It must not be presented as a demonstrated optimization.

## Constraints for any board proposal

- Treat the source facts above separately from performance explanations. The noisy same-source and paired scores do not establish cache conflicts, load stalls, stack reuse, or power-mode causality.
- Keep the frozen 512 FP32 beta-zero workload, arithmetic correctness tolerance, full-call timing, general-size fallback, and complete license text. Keep all packing, conversions, allocation, and SME transitions inside the measured call.
- Avoid repeat candidates equivalent to the tested panel32 wrapper, constant-bound C SME, 272-byte padding, or the three measured K-loop instruction schedules.
- Require exact pointer/leading-dimension equations for any transpose or layout proposal, and preserve fresh paired controls and the existing promotion/holdout gates.

## Evidence paths

- Baseline source and generator context: `evidence/cpu-libxsmm-generator-2026-09-25/baseline/kernel.c`, `generator-review-luna.md`, `layout-review-luna.md`.
- Panel outcomes: `evidence/cpu-libxsmm-panel-swarm-2026-09-25/README.md`, `agent/state.json`, and `search/trial-001..003`.
- Automatic exact-source replay: `evidence/cpu-libxsmm-automatic-2026-09-25/README.md`, `agent/state.json`, and `search/trial-001..003`.
- Previously tested K-loop schedules: `evidence/cpu-libxsmm-next-continue-2026-09-25/README.md` and `search/result.json`.
