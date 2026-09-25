# Luna review of the ahead-of-time adaptation

GPT-6 Luna inspected the generated object, relocations, wrapper, and disassembly. The 2,500-byte generated body has no external calls or relocations. Its local branches resolve inside that body. Relocations in the compiler-generated wrapper and fallback refer to ordinary runtime functions and constants outside it.

The exported parameter slots are 32, 80, and 128 bytes, matching array entries 4, 10, and 16 on this 64-bit target. Passing B, A, C implements the row-major-to-column-major identity. The exported descriptor uses beta=0. The generated prologue and epilogue restore used callee-saved registers, streaming state, stack pointer, and return address. No threading is introduced.

Limits: the n=512 path assumes the verified SME2 target; it has no runtime feature dispatch. Parameter offsets depend on the pinned ABI and 64-bit pointers. The kernel reserves 128 KiB of aligned stack scratch during each outer-loop iteration and restores the stack. This is a bounded local research artifact, not a portable or sandboxed runtime.

The review did not run performance tests. Public correctness and signed scoring are recorded separately.
