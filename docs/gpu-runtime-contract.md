# Checked GPU runtime contract

The release supports the measured `import sera` paths in the existing Linux GPU
environment. A fresh generic GPU install is not a tested release path.

Both services in the passing joint run recorded these package versions:

| Package | Recorded version |
| --- | --- |
| vllm | 0.26.0 |
| torch | 2.11.0 |
| transformers | 5.17.0 |
| flashinfer-python | 0.6.14 |

The sources are the saved [Qwen runtime](../evidence/live-placement-total-v1/trial-001/joint-0/runtime.json)
and [GLM runtime](../evidence/live-placement-total-v1/trial-001/joint-1/runtime.json).
They record an RTX PRO 6000 Blackwell Server Edition, compute capability 12.0,
97,887 MiB physical memory, and driver 595.71.05. The
[earlier environment record](../evidence/qwen-baseline-cuda-link/environment.json)
records Python 3.13.11, Linux x86_64 under gVisor, and the CUDA 13 wheel versions.
That earlier record is not a fresh inventory of the final joint process.

## Installation boundary

Keep the working GPU environment. Install the Sera wheel with the `swarm` extra
there, as described in [the release instructions](simple-release.md). A plain
Sera wheel or `swarm` extra does not install vLLM or CUDA. Importing `sera` does
not load a model, initialize CUDA, or call a provider.

The repository's optional `gpu` extra currently has broad lower bounds. It is
not a reproducible profile: its vLLM range permits versions the Sera runner
rejects. Do not treat `pip install 'sera-inference[gpu]'` alone as a checked
deployment recipe. `SeraModel.start()` requires vLLM 0.26.0 before GPU access;
other package versions are recorded but are not all enforced by that guard.

The release checkout provides [optional package constraints](../constraints/gpu-sm120-tested.txt)
for a separate, deliberate environment build. Use them as a package manager's
`-c` input when preparing that environment. Constraints restrict selected
versions; they do not install packages. This file is not embedded in the wheel,
does not change global package dependencies, and is not proof that a clean
resolver or binary install succeeds. No such install was run for this audit.

## What remains environment-specific

- The constraints are not a full dependency lock. They do not pin every CUDA
  component, package hash, wheel index, or operating-system library.
- The runner has a checked CUDA 13 compiler/header/linker setup path. When the
  `nvidia-cuda-nvcc` wheel is present, it requires `nvcc`, `libcudart.so.13`, and
  available `curand.h` headers. Version pins alone do not prove these files and
  libraries are usable. Missing required files fail startup explicitly.
- The GPU driver is supplied by the host, not pip. Another driver or GPU needs
  its own compatibility check; the recorded version is not a universal minimum.
- Model revisions, workload, generation settings, and memory-accounting mode
  remain part of each experiment's contract. The passing Molab pair used
  explicit total-device accounting because per-service GPU PIDs were not
  available. Package versions do not remove that limitation.
- The clean wheel tests used Python 3.11 on macOS without a GPU. They validate
  packaging and imports, not a fresh Linux/CUDA deployment or arbitrary models.

Run `python -m pytest -q tests/test_gpu_runtime_contract.py` in the release
checkout to compare these constraints with the saved evidence and check that
unsupported vLLM versions are rejected before GPU or server-process access.
This test does not install GPU packages or use the GPU.
