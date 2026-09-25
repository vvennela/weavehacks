"""Fixed advisory roles for single-threaded FP32 CPU GEMM optimization.

The coordinator selects roles by ID. Role text may guide a hypothesis, but it
does not change the workload, benchmark, compiler settings, correctness limit,
search budget, or promotion rule.
"""


DEFAULT_ADVISOR_IDS = (
    "sme_fp32_tiles",
    "sme_fp32_schedule",
    "register_reuse",
    "a_transpose",
    "panel_packing",
    "cache_blocking",
    "vector_access",
    "loop_order",
    "address_generation",
    "compiler_codegen",
    "tail_alignment",
    "scratch_lifetime",
    "prefetch_locality",
    "n512_fast_path",
    "general_c_fallback",
)


ALTERNATE_ADVISOR_IDS = (
    "za_four_tile_reuse",
    "transpose_fusion",
    "k_loop_schedule",
    "b_panel_layout",
    "constant_shape_512",
    "streaming_region_cost",
    "assembly_audit",
    "fp32_sve_fallback",
    "cache_conflict_layout",
    "strassen_one_level",
)


ADVISOR_ROLES = {
    "sme_fp32_tiles": (
        "Study FP32 SME outer-product tile mapping for this CPU. FP32 MOPA has four "
        "ZA.S tile selectors, ZA0.S through ZA3.S; do not propose eight simultaneous "
        "FP32 ZA accumulators. Keep the full output and tail contract."
    ),
    "sme_fp32_schedule": (
        "Study the single-thread FP32 SME MOPA schedule and accumulator dependencies. "
        "Use only the four FP32 ZA tiles and preserve the fixed reduction semantics and tolerance."
    ),
    "register_reuse": (
        "Improve reuse of loaded FP32 input vectors across the current SME output tile. "
        "Account for register pressure and do not assume extra FP32 ZA tiles exist."
    ),
    "a_transpose": (
        "Reduce the cost of making row-major A usable by the FP32 outer-product kernel. "
        "Compare the full timed cost of transpose, packing, and consumption for all supported n."
    ),
    "panel_packing": (
        "Test a bounded FP32 A or B panel layout that improves useful reuse. Include allocation, "
        "packing, tails, and cleanup in the measured call."
    ),
    "cache_blocking": (
        "Choose FP32 GEMM loop and cache blocks for the supplied CPU profile and n=512 workload. "
        "Do not claim a cache bottleneck without matching evidence."
    ),
    "vector_access": (
        "Improve contiguous FP32 loads and stores for the supplied SME or general C path. "
        "Use only capabilities stated in the hardware profile and prove alignment before relying on it."
    ),
    "loop_order": (
        "Compare legal single-thread loop orders for row-major FP32 GEMM. Preserve every output, "
        "the declared ABI, and the full reduction over k."
    ),
    "address_generation": (
        "Reduce pointer updates, index arithmetic, and branches in the FP32 inner loops. "
        "Keep bounds safe for all supported dimensions and retain a correct tail path."
    ),
    "compiler_codegen": (
        "Inspect how the fixed compiler lowers this FP32 kernel and propose source changes that "
        "improve its code. Do not change compiler, flags, or benchmark configuration."
    ),
    "tail_alignment": (
        "Improve FP32 tail and alignment handling without assuming n is a multiple of vector width. "
        "Preserve correctness for all required shapes and do not read or write outside buffers."
    ),
    "scratch_lifetime": (
        "Reduce per-call FP32 scratch allocation and initialization cost. Do not retain state, "
        "cache answers, or make the kernel non-reentrant."
    ),
    "prefetch_locality": (
        "Evaluate FP32 prefetch and access locality for the supplied CPU. Tie each proposal to "
        "recorded workload or hardware evidence and include prefetch overhead in timing."
    ),
    "n512_fast_path": (
        "Consider an n=512 FP32 fast path with a general correct fallback. Keep the benchmark "
        "workload unchanged and validate both the fast path and fallback."
    ),
    "general_c_fallback": (
        "Improve the portable general C FP32 fallback for unsupported SME hardware and edge shapes. "
        "Keep it single-threaded, ABI-compatible, and correct for every supported n."
    ),
    "za_four_tile_reuse": (
        "Revisit output mapping across the four available FP32 ZA.S tiles. Improve reuse or "
        "schedule across ZA0.S through ZA3.S; eight simultaneous FP32 ZA tiles are not available."
    ),
    "transpose_fusion": (
        "Test whether a small FP32 A transpose tile can feed MOPA before it is written to full "
        "scratch. Count repeated transpose work and all data movement in the timed call."
    ),
    "k_loop_schedule": (
        "Propose a distinct FP32 reduction-loop schedule using evidence from generated code. "
        "Earlier two-step and four-step variants did not establish a gain; do not repeat them unchanged."
    ),
    "b_panel_layout": (
        "Test whether packing a row-major FP32 B panel improves the SME consumer enough to pay "
        "for packing. Preserve the same values and include panel setup in timing."
    ),
    "constant_shape_512": (
        "Evaluate a compile-time-specialized FP32 n=512 kernel with a general fallback. "
        "Keep the measured workload and all correctness checks unchanged."
    ),
    "streaming_region_cost": (
        "Examine SME streaming-region entry, exit, and ZA setup costs around this FP32 GEMM. "
        "Use valid language and ABI boundaries and measure the complete call."
    ),
    "assembly_audit": (
        "Read compiler output for this FP32 SME or C kernel and identify one concrete bottleneck "
        "visible in instructions. Do not infer timing from instruction count alone."
    ),
    "fp32_sve_fallback": (
        "Explore an SVE or NEON FP32 fallback only when the supplied CPU profile exposes it. "
        "Keep SME dispatch capability-safe and preserve the general C fallback."
    ),
    "cache_conflict_layout": (
        "Study FP32 scratch stride and cache-set conflicts for the named CPU and dimensions. "
        "Padding must remain in bounds and its full allocation and traffic cost must be measured."
    ),
    "strassen_one_level": (
        "Advise on the user-approved single-level 512-to-256 FP32 Strassen path. "
        "Check all seven-product equations, recombination signs, and row-major mapping "
        "to a dense 256-square NN beta-zero helper. Keep packing, allocation, products, "
        "and recombination inside the timed call; preserve tolerance and the general fallback. "
        "Account for FP32 rounding risk and packing quadrants whose parent stride is 512. "
        "Do not propose deeper recursion, Winograd, mixed precision, or policy changes."
    ),

}
