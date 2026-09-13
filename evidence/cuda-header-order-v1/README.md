# Compile-only CUDA header check: passed

No model or GPU kernel was executed. A small CUDA source included `curand.h` and defined a kernel launch, then compiled with the actual Molab CUDA 13.0 compiler.

- Mixed `-I` and `-isystem` paths reproduced the runtime-header macro error: exit 1.
- Compiler-first `-isystem` paths found both the matching compiler header and base-environment cuRAND: exit 0.

The full commands, injected flags, compiler output, and exit codes are saved in `result.json`. This validates the compiler-path repair, not inference, task quality, or performance. The production fix is `ae81606`.
